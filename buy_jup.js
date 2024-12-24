const fs = require('fs');
const path = require('path');
const { Command } = require('commander');
const axios = require('axios');
const { createClient } = require('@supabase/supabase-js');
const dotenv = require('dotenv');
const winston = require('winston');
const SolanaAgentKit = require('solana-agent-kit'); // Corrected Import
const bs58 = require('bs58');
const web3 = require('@solana/web3.js'); // Added Import for web3

// Load environment variables from .env file
dotenv.config();
const privKey = process.env.AGENT_PRIVATE_KEY;
if (!privKey) throw new Error("no privkey")

let privateKeyArray;
try {
    privateKeyArray = JSON.parse(privKey);
    console.log(privateKeyArray)
    if (!Array.isArray(privateKeyArray)) {
        throw new Error("Private key is not an array.");
    }
    
} catch (error) {
    throw new Error("Failed to parse the private key. Ensure it's a valid JSON array string.");
}
const keypair = web3.Keypair.fromSecretKey(Uint8Array.from(privateKeyArray));
console.log("bs58 nf", bs58)
const secretKeyBase58 = bs58.default.encode(keypair.secretKey);
const rpcUrl = process.env.RPC_URL
if (!rpcUrl) throw new Error("no RPC")

const gptKey = process.env.OPENAI_API_KEY;
if (!gptKey) throw new Error("no OAI KEY")

    // Initialize with private key and optional RPC URL
const agent = new SolanaAgentKit.SolanaAgentKit(
    secretKeyBase58,
    rpcUrl,
    gptKey
);
  



// Configure Winston Logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.printf(({ timestamp, level, message }) => {
          return `${timestamp} [${level.toUpperCase()}]: ${message}`;
      })
  ),
  transports: [
    new winston.transports.Console(),
    // You can add more transports like File if needed
  ],
});

// Retrieve Supabase credentials from environment variables
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_KEY;

if (!SUPABASE_URL || !SUPABASE_KEY) {
    throw new Error("Missing Supabase credentials in environment variables.");
}

// Initialize Supabase client
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);

/**
 * Fetches the current price for the given mint from Jupiter's Price API V2.
 * Returns 0.0 if any error occurs.
 * @param {string} mint - The mint address of the token.
 * @returns {Promise<number>}
 */
async function fetchJupiterPrice(mint) {
    try {
        const url = `https://api.jup.ag/price/v2?ids=${mint}`;
        const response = await axios.get(url, { timeout: 10000 });

        if (response.status === 200) {
            const data = response.data;
            return parseFloat(data.data[mint].price);
        } else {
            logger.warn(`Jupiter returned status ${response.status} for mint=${mint}`);
        }
    } catch (error) {
        logger.error(`Error fetching Jupiter price for mint=${mint}: ${error.message}`, { stack: error.stack });
    }
    return 0.0;
}

/**
 * Inserts a row into the 'portfolio' table indicating we hold this token.
 * @param {string} mint - The mint address of the token.
 * @param {number} buyPrice - The price at which the token was bought.
 * @param {number} quantity - The quantity of the token bought.
 */
async function insertPortfolioEntry(mint, buyPrice, quantity) {
    try {
        // Attempt to find a coin_uuid from 'coins' table, if it exists
        let coin_uuid = null;
        try {
            const { data, error } = await supabase
                .from('coins')
                .select('id')
                .eq('mint', mint)
                .limit(1);

            if (error) {
                throw error;
            }

            if (data && data.length > 0) {
                coin_uuid = data[0].id;
            }
        } catch (error) {
            logger.error(`Unable to find coin_uuid for mint=${mint}, continuing without it. Error: ${error.message}`, { stack: error.stack });
        }

        const insertData = {
            mint: mint,
            price: buyPrice,
            quantity: quantity,
            inpossession: true,
        };

        if (coin_uuid) {
            insertData.coin_uuid = coin_uuid;
        }

        const { error } = await supabase
            .from('portfolio')
            .insert(insertData);

        if (error) {
            throw error;
        }

        logger.info(`Inserted into portfolio => mint=${mint}, price=${buyPrice}, qty=${quantity}, coin_uuid=${coin_uuid}`);
    } catch (error) {
        logger.error(`Error inserting into portfolio table: ${error.message}`, { stack: error.stack });
    }
}

/**
 * Placeholder for the real buy process.
 * Executes a real buy order on-chain.
 * Returns true if the transaction was successful, false otherwise.
 * @param {string} mint - The mint address of the token.
 * @returns {Promise<boolean>}
 */
async function executeRealBuy(mint) {
    try {
        logger.info(`Executing real buy for mint: ${mint}`);

        const signature = await SolanaAgentKit.trade(
            agent,
         //   new web3.PublicKey(mint),
         mint,  
         100, // amount
            new web3.PublicKey("So11111111111111111111111111111111111111112"),
            300 
          );
        console.log("signature", signature)   

    } catch (error) {
        logger.error(`Error executing real buy for mint=${mint}: ${error.message}`, { stack: error.stack });
        return false;
    }
}

/**
 * Parses command-line arguments using Commander.
 * @returns {Object} Parsed arguments.
 */
function parseArguments() {
    const program = new Command();

    program
        .argument('[mint]', 'Mint address of the token to buy')
        .option('--mode <mode>', 'Mode of operation: "simulate" for fake buy, "real" for actual buy', 'simulate')
        .parse(process.argv);

    const args = program.args;
    const options = program.opts();

    return {
        mint: args[0],
        mode: options.mode,
    };
}

// Main Execution Flow
(async () => {
    const { mint, mode } = parseArguments();

    if (mint) {
        logger.info(`[BUY PLACEHOLDER] Buying token with mint: ${mint}`);

        // 1) Fetch Jupiter price
        //const curPrice = await fetchJupiterPrice(mint);

        // 2) Insert into portfolio with quantity=500000
       //const defaultQty = 500000.0;
        //await insertPortfolioEntry(mint, curPrice, defaultQty);

        // 3) If mode is 'real', execute the real buy
        if (mode === 'real') {
            console.log(mint)
            const success = await executeRealBuy(mint);
            if (success) {
                logger.info("Real buy order executed successfully.");
            } else {
                logger.error("Real buy order failed.");
            }
        }
    } else {
        logger.info("[BUY PLACEHOLDER] No mint provided, but simulating buy.");
    }

    logger.info("Operation completed.");
})();

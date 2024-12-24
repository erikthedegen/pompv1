/* File: /pompv1/frontend/livechat.js */

let supabase; // We'll instantiate after fetching /livechat_config
let messagesSubscription;

// In-memory map for username -> color
const userColorMap = {};

// HTML elements
const connectWalletBtn = document.getElementById("connectWalletBtn");
const messagesList = document.getElementById("messagesList");
const chatContainer = document.getElementById("chatContainer");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const slowModeWarning = document.getElementById("slowModeWarning");

/************************************************************
 * HELPER FUNCTIONS
 ************************************************************/
function showWarning(msg, doShake = false) {
  slowModeWarning.textContent = msg;
  slowModeWarning.style.display = "block";

  if (doShake) {
    slowModeWarning.classList.add("shake");
    setTimeout(() => slowModeWarning.classList.remove("shake"), 300);
  }

  // Hide after 1.5s
  setTimeout(() => {
    slowModeWarning.style.display = "none";
  }, 1500);
}

function generateRandomColor() {
  return "#" + Math.floor(Math.random() * 16777215).toString(16).padStart(6, "0");
}

/**
 * Use first 5 letters of wallet publicKey + '...'
 */
function shortUsernameFromPubkey(pubkey) {
  if (!pubkey || pubkey.length < 5) return "?????";
  return pubkey.slice(0, 5) + "...";
}

/**
 * Retrieves or creates a user in 'users' table
 */
async function getOrCreateUser(publicKey) {
  // Check localStorage
  const existingStr = localStorage.getItem("myLivechatUser");
  if (existingStr) {
    const existingUser = JSON.parse(existingStr);
    if (existingUser.walletpublickey === publicKey) {
      return existingUser;
    }
  }

  // Query supabase
  const { data: userRecord, error } = await supabase
    .from("users")
    .select("*")
    .eq("walletpublickey", publicKey)
    .single();

  if (error && error.code !== "PGRST116") {
    console.error("Error fetching user:", error);
  }

  if (userRecord) {
    localStorage.setItem("myLivechatUser", JSON.stringify(userRecord));
    return userRecord;
  } else {
    // Insert new user
    const newUsername = shortUsernameFromPubkey(publicKey);
    const { data: newUser, error: insertError } = await supabase
      .from("users")
      .insert([{ walletpublickey: publicKey, username: newUsername }])
      .select()
      .single();

    if (insertError) {
      console.error("Error inserting user:", insertError);
      alert("Failed to create user in database.");
      return null;
    }
    localStorage.setItem("myLivechatUser", JSON.stringify(newUser));
    return newUser;
  }
}

function assignUserColor(username) {
  if (!userColorMap[username]) {
    userColorMap[username] = generateRandomColor();
  }
  return userColorMap[username];
}

/**
 * Display a new message in the chat UI
 */
function addMessageToUI(username, content) {
  const color = assignUserColor(username);

  const li = document.createElement("li");
  const userSpan = document.createElement("span");
  userSpan.classList.add("username");
  userSpan.style.color = color;
  userSpan.textContent = username + ":";

  const contentSpan = document.createElement("span");
  contentSpan.textContent = " " + content;

  li.appendChild(userSpan);
  li.appendChild(contentSpan);
  messagesList.appendChild(li);

  // auto-scroll
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Fetch the last 50 messages and render them
 */
async function fetchExistingMessages() {
  const { data: messages, error } = await supabase
    .from("messages")
    .select("content, created_at, user_id, users(username)")
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    console.error("Error fetching messages:", error);
    return;
  }

  // Reverse for chronological
  if (messages) {
    const reversed = messages.reverse();
    reversed.forEach((msg) => {
      addMessageToUI(msg.users.username, msg.content);
    });
  }
}

/**
 * Subscribe to realtime message inserts
 */
function subscribeToMessages() {
  messagesSubscription = supabase
    .channel("public:messages")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "messages" },
      (payload) => {
        const newMsg = payload.new;
        if (!newMsg) return;
        fetchUserAndRenderMessage(newMsg);
      }
    )
    .subscribe((status) => {
      if (status === "SUBSCRIBED") {
        console.log("Livechat subscription active for messages.");
      }
    });
}

/**
 * Fetch user for the new message row, then display
 */
async function fetchUserAndRenderMessage(msgRow) {
  const { data: userData, error } = await supabase
    .from("users")
    .select("username")
    .eq("id", msgRow.user_id)
    .single();

  if (error) {
    console.error("Error fetching user for message:", error);
    return;
  }
  addMessageToUI(userData.username, msgRow.content);
}

/************************************************************
 * EVENT HANDLERS
 ************************************************************/
connectWalletBtn.addEventListener("click", async () => {
  if (window.solana && window.solana.isPhantom) {
    try {
      const response = await window.solana.connect({ onlyIfTrusted: false });
      const publicKey = response.publicKey.toString();
      console.log("Connected with Phantom publicKey:", publicKey);

      // get or create user
      const user = await getOrCreateUser(publicKey);
      if (user) {
        alert(`Wallet connected! Your chat name is ${user.username}`);
      }
    } catch (err) {
      console.error("Phantom connection error:", err);
      alert("Could not connect Phantom wallet.");
    }
  } else {
    alert("Phantom wallet extension not found!");
  }
});

sendBtn.addEventListener("click", sendMessage);
chatInput.addEventListener("keyup", (e) => {
  if (e.key === "Enter") {
    sendMessage();
  }
});

/**
 * Insert a message if slow mode & length checks pass
 */
async function sendMessage() {
  const userStr = localStorage.getItem("myLivechatUser");
  if (!userStr) {
    showWarning("Please connect your wallet first!", true);
    return;
  }
  const userData = JSON.parse(userStr);

  let content = chatInput.value.trim();
  if (!content) return;
  if (content.length > 50) {
    showWarning("Message too long (max 50 chars)!", true);
    return;
  }

  // Slow mode check
  const { data: freshUser, error: fetchError } = await supabase
    .from("users")
    .select("*")
    .eq("id", userData.id)
    .single();

  if (fetchError) {
    console.error("Error fetching user for slow mode:", fetchError);
    return;
  }

  const lastMessageAt = freshUser.last_message_at
    ? new Date(freshUser.last_message_at)
    : null;
  const now = new Date();

  if (lastMessageAt) {
    const diffInSeconds = (now - lastMessageAt) / 1000;
    if (diffInSeconds < 2) {
      showWarning("Slow mode: please wait 2s!", true);
      return;
    }
  }

  // Insert the message
  const { error: insertError } = await supabase
    .from("messages")
    .insert([{ user_id: freshUser.id, content }]);

  if (insertError) {
    console.error("Error inserting message:", insertError);
    showWarning("Error sending message!", true);
    return;
  }

  // Update last_message_at
  const { data: updatedUser, error: updateError } = await supabase
    .from("users")
    .update({ last_message_at: now.toISOString() })
    .eq("id", freshUser.id)
    .select()
    .single();

  if (updateError) {
    console.error("Error updating last_message_at:", updateError);
  } else {
    localStorage.setItem("myLivechatUser", JSON.stringify(updatedUser));
  }

  // Clear input
  chatInput.value = "";
}

/************************************************************
 * INIT
 ************************************************************/
window.addEventListener("DOMContentLoaded", async () => {
  try {
    // 1) Fetch supabase config from Flask route
    const res = await fetch("/livechat_config");
    const configData = await res.json();

    // 2) Create supabase client
    supabase = window.supabase.createClient(
      configData.SUPABASE_URL,
      configData.SUPABASE_ANON_KEY
    );

    // 3) Fetch existing messages & subscribe
    await fetchExistingMessages();
    subscribeToMessages();
  } catch (err) {
    console.error("Failed to load /livechat_config:", err);
    alert("Could not load livechat config from server.");
  }
});

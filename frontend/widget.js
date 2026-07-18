const send = document.getElementById("send");
const input = document.getElementById("message");
const messages = document.getElementById("messages");
const chatContainer = document.getElementById("chatContainer");
const chatLauncher = document.getElementById("chatLauncher");
const chatClose = document.getElementById("chatClose");

const suggestions = document.querySelectorAll(".suggestion");
let chatContext = {};

// Live backend endpoint. Override by setting window.ZYRALUXE_API before this
// script loads (e.g. in index.html) so you don't have to edit widget.js to redeploy.
const API_URL = (window.ZYRALUXE_API || "https://zyraluxe-ai-chatbot.onrender.com") + "/chat";
// ================================
// Widget Open / Close
// ================================

function openChat(){

    chatContainer.classList.add("is-open");
    chatContainer.setAttribute("aria-hidden", "false");
    chatLauncher.classList.add("is-hidden");
    input.focus();
    scrollBottom();

}

function closeChat(){

    chatContainer.classList.remove("is-open");
    chatContainer.setAttribute("aria-hidden", "true");
    chatLauncher.classList.remove("is-hidden");

}

chatLauncher.addEventListener("click", openChat);
chatClose.addEventListener("click", closeChat);


// ================================
// Scroll
// ================================

function scrollBottom(){

    messages.scrollTop = messages.scrollHeight;

}


// ================================
// User Message
// ================================

function addUserMessage(text){

    messages.innerHTML += `

    <div class="user-message">

        ${text}

    </div>

    `;

    scrollBottom();

}


// ================================
// AI Typing
// ================================

function showTyping(){

    messages.innerHTML += `

    <div
        class="ai-message loading"
        id="typing"
    >

        <span></span>

        <span></span>

        <span></span>

    </div>

    `;

    scrollBottom();

}


function removeTyping(){

    const typing = document.getElementById("typing");

    if(typing){

        typing.remove();

    }

}


// ================================
// AI Reply
// ================================

function addAIMessage(reply){

    messages.innerHTML += `

    <div class="ai-message">

        ${reply.replace(/\n/g,"<br>")}

    </div>

    `;

    scrollBottom();

}



// ================================
// Product Card
// ================================

function escapeHTML(value){

    return String(value || "")

        .replace(/&/g, "&amp;")

        .replace(/</g, "&lt;")

        .replace(/>/g, "&gt;")

        .replace(/"/g, "&quot;")

        .replace(/'/g, "&#039;");

}

function cleanDescription(description){

    const template = document.createElement("template");

    template.innerHTML = description || "";

    template.content.querySelectorAll("img, picture, source, figure, video, iframe, script, style").forEach(element=>{

        element.remove();

    });

    return template.content.textContent

        .replace(/\s+/g, " ")

        .trim();

}

function ratingRow(product){

    const ratingValue = Number(product.rating || 0);
    const ratingCount = Number(product.rating_count || 0);
    const roundedRating = Math.round(ratingValue);
    const stars = Array.from({length:5}, (_, index)=>{

        const active = index < roundedRating ? " active" : "";

        return `<span class="rating-star${active}">&#9733;</span>`;

    }).join("");
    const label = ratingCount > 0

        ? `${ratingValue.toFixed(1)} (${ratingCount} reviews)`

        : "No reviews yet";

    return `

        <div class="rating-row" aria-label="Product rating ${label}">

            <span class="rating-stars">${stars}</span>

            <span class="rating-text">${label}</span>

        </div>

    `;

}

function productCard(product){

    const description = escapeHTML(cleanDescription(product.description));
    const productName = escapeHTML(product.name);
    const productCategory = escapeHTML(product.category);

    const image = product.image

    ? product.image

    : "https://placehold.co/600x500?text=No+Image";

    const stock =

        product.stock==="instock"

        ? `<span class="badge stock">In Stock</span>`

        : `<span class="badge out">Out of Stock</span>`;

    return `

    <div class="product-card">

        <img src="${image}">

        <div class="product-info">

            <h3>${productName}</h3>

            ${ratingRow(product)}

            <div class="price">

                &#8377;${product.price}

            </div>

            <div class="badges">

                ${stock}

                <span class="badge category">

                    ${productCategory}

                </span>

            </div>

            <div class="description">

                ${description}

            </div>

            <a

                href="${product.url}"

                target="_blank"

                class="view-btn"

            >

                View Product

            </a>

        </div>

    </div>

    `;

}



// ================================
// Send
// ================================

async function sendMessage(customText=null){

    const text = customText || input.value.trim();

    if(text==="") return;

    addUserMessage(text);

    input.value="";

    showTyping();

    try{

        const response = await fetch(

            API_URL,

            {

                method:"POST",

                headers:{

                    "Content-Type":"application/json"

                },

                body:JSON.stringify({

                    message:text,

                    context:chatContext

                })

            }

        );

        if(!response.ok){

            throw new Error(

                "Server Error"

            );

        }

        const data = await response.json();

        chatContext = data.context || {};

        removeTyping();

        addAIMessage(data.reply);

        if(data.products.length){

            messages.innerHTML+=`

            <div class="results-header">

                Showing

                <b>

                ${data.products.length}

                </b>

                recommendations

            </div>

            `;

            data.products.forEach(product=>{
 
                messages.innerHTML +=
 
                productCard(product);
 
            });

            // "Show more" button — re-sends the previous search with a larger
            // limit. chatContext already carries last_query/last_limit.
            if(data.context && data.context.last_query){
 
                messages.innerHTML += `
 
                <button type="button" class="show-more-btn" id="showMoreBtn">
 
                    Show more products
 
                </button>
 
                `;
 
                const moreBtn = document.getElementById("showMoreBtn");
 
                if(moreBtn){
 
                    moreBtn.addEventListener("click", ()=> sendMessage("more"));
 
                }
 
            }
 
        }
        else if(data.query && data.query.intent === "shopping" && !(data.context && data.context.mode)){

            messages.innerHTML += `

            <div class="ai-message">

                No matching products found.

            </div>

            `;

        }

        scrollBottom();

    }

    catch(error){

        removeTyping();

        messages.innerHTML += `

        <div class="ai-message">

            Sorry, 

            ${error.message}

        </div>

        `;

    }

}



// ================================
// Events
// ================================

send.addEventListener(

"click",

()=>{

sendMessage();

}

);

input.addEventListener(

"keypress",

e=>{

if(e.key==="Enter"){

sendMessage();

}

}

);



// ================================
// Suggestions
// ================================

suggestions.forEach(btn=>{

btn.addEventListener(

"click",

()=>{

sendMessage(

btn.innerText

);

}

);

});














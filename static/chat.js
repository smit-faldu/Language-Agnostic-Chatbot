let sessionId = localStorage.getItem('sessionId') || Math.random().toString(36).substr(2, 9);
localStorage.setItem('sessionId', sessionId);

const chatContainer = document.getElementById('chat-container');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');

function addMessage(text, isUser = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'p-3 rounded-lg max-w-xs ' + (isUser ? 'bg-blue-500 text-white self-end ml-auto' : 'bg-white text-gray-800');
    messageDiv.textContent = text;
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function createPdfPreview(fileName, pageNumber = 1) {
    const previewDiv = document.createElement('div');
    previewDiv.className = 'my-2'; // Simple margin
    
    const pdfUrl = `/data/${fileName}`;

    const openButton = document.createElement('button');
    // Using Tailwind classes for styling
    openButton.className = 'bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded';
    openButton.textContent = `Open ${fileName}`;
    openButton.onclick = () => window.open(pdfUrl, '_blank');
    
    previewDiv.appendChild(openButton);
    
    return previewDiv;
}

function sendQuery() {
    const query = queryInput.value.trim();
    if (!query) return;
    addMessage(query, true);
    queryInput.value = '';

    fetch('/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: query, session_id: sessionId })
    })
    .then(response => response.json())
    .then(data => {
        addMessage(data.answer);
        
        // Add source information if available
        if (data.sources && data.sources.length > 0) {
            data.sources.forEach(source => {
                if (source.filename && source.filename.toLowerCase().endsWith('.pdf')) {
                    const pdfPreview = createPdfPreview(source.filename, source.page || 1);
                    chatContainer.appendChild(pdfPreview);
                }
            });
        }
        
        chatContainer.scrollTop = chatContainer.scrollHeight;
    })
    .catch(error => {
        addMessage('Sorry, an error occurred.', false);
        console.error('Error:', error);
    });
}

sendBtn.addEventListener('click', sendQuery);
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendQuery();
});

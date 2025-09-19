import React, { useState, useRef, useEffect } from 'react';

const ChatWidget = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "נסו אותי ↓",
      isBot: true,
      isClickable: true,
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);

  // Ref for the messages container and input
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Scroll to bottom when messages change or loading changes
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollTop = messagesEndRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Handle click on "נסו אותי" message
  const handleTryMeClick = () => {
    // Focus on input field
    if (inputRef.current) {
      inputRef.current.focus();
    }
    // Scroll to input area smoothly
    const inputContainer = inputRef.current?.parentElement?.parentElement;
    if (inputContainer) {
      inputContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  };

  // פונה לשרת Flask שלך לקבלת תשובה מהבוט
// שולף תשובת בוט מהשרת (מותאם ל-local ול-production)
const fetchBotReply = async (message) => {
  try {
    const apiUrl = import.meta.env.VITE_API_BASE_URL
      ? `${import.meta.env.VITE_API_BASE_URL}/chat`
      : '/api/chat';

    // הדפסה לבדיקה:
    console.log("API_URL:", apiUrl);

    const res = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question: message }),
      credentials: 'include', // שומר על session/cookies אם צריך
    });

    const data = await res.json();
    return data.answer || "לא התקבלה תשובה 😕";

  } catch (err) {
    console.error("שגיאה:", err);
    return "הייתה בעיה בהתחברות לבוט. נסה שוב מאוחר יותר.";
  }
};

  // שליחת הודעה
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const newMessage = {
      id: messages.length + 1,
      text: inputValue,
      isBot: false,
    };

    setMessages((prev) => [...prev, newMessage]);
    setInputValue('');
    setLoading(true);

    // קבלת תגובת בוט אמיתית מהשרת
    const botText = await fetchBotReply(inputValue);
    const botResponse = {
      id: messages.length + 2,
      text: botText,
      isBot: true,
    };

    setMessages((prev) => [...prev, botResponse]);
    setLoading(false);
  };

  // Animated loading dots component
  const LoadingDots = () => (
    <div className="flex justify-start">
      <div className="chat-bubble bot text-left flex items-center px-4 py-3">
        <span className="inline-block animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
        <span className="inline-block animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
        <span className="inline-block animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
      </div>
    </div>
  );

  return (
    <div className="bg-card rounded-xl shadow-lg border border-border h-[600px] flex flex-col text-right" dir="rtl">
      {/* Chat Header */}
      <div className="p-4 border-b border-border bg-muted/20 rounded-t-xl">
        <div className="flex flex-row items-center space-x-reverse space-x-3 justify-start">
          <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center ml-3">
            <i className="fas fa-robot text-primary-foreground"></i>
          </div>
          <div className="text-right">
            <h3 className="font-semibold">Atarize AI Assistant</h3>
            <p className="text-sm text-muted-foreground">מחובר</p>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div ref={messagesEndRef} className="flex-1 p-4 space-y-4 overflow-y-auto">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.isBot ? 'justify-start' : 'justify-end'}`} dir="rtl">
            <div 
              className={`chat-bubble ${message.isBot ? 'bot text-left' : 'user text-right'} px-4 py-3 ${
                message.isClickable ? 'cursor-pointer hover:opacity-80 transition-opacity font-bold' : ''
              }`}
              onClick={message.isClickable ? handleTryMeClick : undefined}
            > 
              {message.text} 
            </div>
          </div>
        ))}
        {loading && <LoadingDots />}
      </div>

      {/* Chat Input */}
      <div className="p-4 border-t border-border rounded-b-xl">
        <form onSubmit={handleSendMessage} className="flex flex-row items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="הקלד את ההודעה שלך..."
            className="flex-1 px-4 py-3 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent bg-background text-right"
            dir="rtl"
          />
          <button
            type="submit"
            className="px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity ml-2"
            disabled={loading}
          >
            <i className="fas fa-paper-plane"></i>
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatWidget;
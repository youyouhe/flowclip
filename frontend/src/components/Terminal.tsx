import { useEffect, useState, useRef } from 'react';

// Fix for NodeJS.Timeout type in browser environment
type Timeout = ReturnType<typeof setTimeout>;

const Terminal = () => {
  const [terminalText, setTerminalText] = useState('');
  const [cursorVisible, setCursorVisible] = useState(true);
  const [animationComplete, setAnimationComplete] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Terminal animation sequence
  useEffect(() => {
    const lines = [
      { text: "$ ", delay: 500 },
      { text: "youtube-analyzer --input https://youtube.com/watch?v=example", delay: 80, finalDelay: 600 },
      { text: "\n📥 Downloading video...", delay: 50, finalDelay: 400 },
      { text: "\n🎵 Extracting audio...", delay: 50, finalDelay: 400 },
      { text: "\n🎤 Processing audio tracks...", delay: 50, finalDelay: 500 },
      { text: "\n🤖 Generating transcript with AI...", delay: 50, finalDelay: 600 },
      { text: "\n✂️ Auto-slicing content...", delay: 50, finalDelay: 500 },
      { text: "\n📝 Creating subtitles...", delay: 50, finalDelay: 400 },
      { text: "\n✅ Analysis complete! Ready for exploration.", delay: 50, finalDelay: 0 }
    ];

    let currentText = '';
    let timeoutId: Timeout;
    let currentLineIndex = 0;
    let currentCharIndex = 0;

    const typeNextChar = () => {
      if (currentLineIndex >= lines.length) {
        setAnimationComplete(true);
        return;
      }

      const currentLine = lines[currentLineIndex];
      
      if (currentCharIndex < currentLine.text.length) {
        currentText += currentLine.text[currentCharIndex];
        setTerminalText(currentText);
        currentCharIndex++;
        
        timeoutId = setTimeout(typeNextChar, currentLine.delay);
      } else {
        currentLineIndex++;
        currentCharIndex = 0;
        timeoutId = setTimeout(typeNextChar, currentLine.finalDelay || 0);
      }

      // Ensure terminal scrolls to bottom as text is added
      if (terminalRef.current) {
        terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
      }
    };

    timeoutId = setTimeout(typeNextChar, 1000);

    return () => clearTimeout(timeoutId);
  }, []);

  // Cursor blink effect
  useEffect(() => {
    if (animationComplete) {
      const blinkInterval = setInterval(() => {
        setCursorVisible(prev => !prev);
      }, 500);

      return () => clearInterval(blinkInterval);
    }
  }, [animationComplete]);

  return (
    <div className="terminal max-w-3xl mx-auto my-8 opacity-0 animate-fade-in">
      <div className="terminal-header">
        <div className="terminal-button close-button"></div>
        <div className="terminal-button minimize-button"></div>
        <div className="terminal-button maximize-button"></div>
        <div className="ml-auto text-xs text-gray-400">youtube-slicer-terminal</div>
      </div>
      <div 
        ref={terminalRef}
        className="terminal-content text-sm md:text-base text-green-400 font-mono mt-2 h-48 overflow-hidden"
      >
        {terminalText}
        <span className={`cursor ${cursorVisible ? 'opacity-100' : 'opacity-0'}`}></span>
      </div>
    </div>
  );
};

export default Terminal;
// The terminal on the Console, Attach and Terminal pages (xterm.js 6 + the fit addon).
//
// Protocol (xterm/consumers.py): keys, paste and IME input go up as "pty_input" {input}, the size
// as "pty_resize" {size: {rows, cols, width, height}}; whatever the server sends is written to
// the terminal. Ctrl+C (Cmd+C on a Mac) copies when text is selected, and is sent otherwise.
function openTerminalSession({ socketPath, protocol, onOpen }) {
    const element = document.getElementById('terminal');
    const status = document.getElementById('status');
    const term = new Terminal({
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(element);
    fitAddon.fit();

    const socket = openSocket(socketPath, protocol);
    const send = (action, payload) => {
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ action, payload }));
        }
    };
    const sendSize = () => send('pty_resize', {
        size: { rows: term.rows, cols: term.cols, width: element.offsetWidth, height: element.offsetHeight },
    });

    const isMac = navigator.platform.toUpperCase().includes('MAC');
    term.attachCustomKeyEventHandler((event) => {
        const copyKey = isMac ? event.metaKey : event.ctrlKey;
        if (event.type === 'keydown' && copyKey && event.key === 'c' && term.hasSelection()) {
            navigator.clipboard.writeText(term.getSelection());
            return false;
        }
        return true;
    });
    term.onData((data) => send('pty_input', { input: data }));
    term.onResize(debounce(sendSize, 250));
    window.addEventListener('resize', debounce(() => fitAddon.fit(), 100));

    socket.onopen = () => {
        status.textContent = 'connected';
        status.className = 'connected';
        if (onOpen) {
            onOpen(send);
        }
        sendSize();
        term.focus();
    };
    socket.onmessage = (event) => term.write(event.data);
    socket.onclose = () => {
        status.textContent = 'disconnected';
        status.className = 'disconnected';
        term.write('\r\n\n[Connection closed]\r\n');
        term.options.cursorBlink = false;
        term.options.disableStdin = true;
        term.options.theme = { background: '#1e1e1e', foreground: '#707070' };
    };
    return { term, socket };
}

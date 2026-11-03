// Terminal page: bash inside this app's own container (superusers only).
document.addEventListener('DOMContentLoaded', () => openTerminalSession({
    socketPath: '/ws/terminal/',
    protocol: `terminal.${uniqueID()}`,
}));

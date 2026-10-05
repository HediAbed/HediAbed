Output recordings/bughunter.mp4

Set Shell "bash"
Set FontFamily `"PxPlus IBM VGA 8x16"`
Set FontSize 32
Set Width 1952
Set Height 832
Set Padding 32
Set Framerate 24
Set BorderRadius 0
Set Theme {"background":"#16161a","foreground":"#d8d4cc","cursor":"#d8d4cc","selection":"#3a3a40","black":"#1d1d22","red":"#b4454f","green":"#7a9b76","yellow":"#c9a66b","blue":"#6a8caf","magenta":"#a56a8c","cyan":"#6ba3a0","white":"#d8d4cc","brightBlack":"#8a867f","brightRed":"#e8336f","brightGreen":"#9bc295","brightYellow":"#e0c08a","brightBlue":"#8fb3d9","brightMagenta":"#e8336f","brightCyan":"#8fcac7","brightWhite":"#eceae4"}
Set TypingSpeed 40ms

Hide
Type `export HOME="$RECORD_HOME" PATH="$BUGHUNTER_BIN_DIR:$PATH" BUGHUNTER_BACKEND=openai-compatible BUGHUNTER_API_URL=https://api.minimax.io/v1 BUGHUNTER_MODEL=MiniMax-M2.7-highspeed BUGHUNTER_API_TOKEN="$MINIMAX_API_KEY"; unset NO_COLOR CI; cd "$NODEGOAT_DIR"; rm -f report.json; PS1='\[\033[0;95m\]$\[\033[0m\] '; clear`
Enter
Sleep 500ms
Show

Type "bughunter analyze --project . --with-ai --format json --output report.json"
Sleep 300ms
Enter
Sleep 10500ms
Hide
Ctrl+C
Sleep 500ms

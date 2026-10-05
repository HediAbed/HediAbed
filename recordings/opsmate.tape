Output recordings/opsmate.mp4

Set Shell "bash"
Set FontFamily '"PxPlus IBM VGA 8x16"'
Set FontSize 32
Set Width 1952
Set Height 1344
Set Padding 32
Set Framerate 24
Set BorderRadius 0
Set TypingSpeed 60ms
Set Theme {"background":"#16161a","foreground":"#d8d4cc","cursor":"#d8d4cc","selection":"#3a3a40","black":"#1d1d22","red":"#b3555f","green":"#7a9471","yellow":"#b89a5c","blue":"#5f7a94","magenta":"#8a6f94","cyan":"#5f9499","white":"#d8d4cc","brightBlack":"#8a867f","brightRed":"#e8336f","brightGreen":"#94b388","brightYellow":"#d4b56f","brightBlue":"#7a94b3","brightMagenta":"#e8336f","brightCyan":"#7ab3b8","brightWhite":"#f4f2ee"}

Hide
Type `export HOME="$RECORD_HOME" PATH="$OPSMATE_BIN_DIR:$PATH" KUBECONFIG="$OPSMATE_KUBECONFIG"; unset NO_COLOR; clear`
Enter
Sleep 300ms
Type "opsmate"
Enter
Wait+Screen@20s /CrashLoopBackOff/
Sleep 500ms
Show

Sleep 4500ms
Down
Sleep 1000ms
Down
Sleep 2800ms
Type "l"
Sleep 4500ms
Type "2"
Sleep 3500ms
Type "1"
Sleep 4000ms

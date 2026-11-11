#Requires AutoHotkey v2.0
; [Ctrlキー] ^
; [Shiftキー] +
; [Altキー] !
; [Winキー] #

; vim
F13 & h::Send '{Left}'
F13 & j::Send '{Down}'
F13 & k::Send '{Up}'
F13 & l::Send '{Right}'

F13 & e::Send '^{Right}'
F13 & q::Send '^{Left}'

F13 & d::Send '{Delete}'
F13 & w::Send '^{Backspace}'

F13 & c::Send '^c'
F13 & x::Send '!x'
F13 & s::Send '!s'

; Window snap
#HotIf GetKeyState("Ctrl") ; Ctrlキーが押されている時のみ有効化
    F13 & Right::Send '#{Right}'
    F13 & Left::Send '#{Left}'
    F13 & Up::Send '#{Up}'
    F13 & Down::Send '#{Down}'
#HotIf ; ホットキーの条件を解除

; window switch
F13 & TAB::Send '{Blind}^{TAB}'
Ctrl & TAB::Send '!{TAB}'

; colon to semicolon
VKBA::+VKBA
+VKBA::VKBA

; disable Alt
*~Alt::Send '{Blind}{vk07}'

~LAlt::
{
    SendInput "{Blind}{sc0E9}"
    KeyWait "LAlt"
    SendInput "{Blind}{sc0EA}"
}

~RAlt::
{
    SendInput "{Blind}{sc0E9}"
    KeyWait "RAlt"
    SendInput "{Blind}{sc0EA}"
}

; clipboard history
F13 & v::Send '#{v}'

F13 & a::Send '^{b}'

; F13 + S でSlack開く設定
; F13 & s::
; {
;     if WinActive("Slack")
;         WinMinimize("Slack") ; すでにアクティブな場合は背面（最小化）
;     else if WinExist("Slack")
;         WinActivate ; 開いているがアクティブでない場合はフォーカス
;     else
;         Run("C:\Program Files\WindowsApps\91750D7E.Slack_4.47.69.0_x64__8she8kybcnzg4\app\Slack.exe") ; 開いていない場合は新しく起動
; }

; F13 + F でVSCode開く設定
F13 & f::
{
    if WinActive("Visual Studio Code")
    {
        if WinExist("Google Chrome")
            WinActivate("Google Chrome")
        else
            Run("C:\Program Files\Google\Chrome\Application\chrome.exe")
    }
    else if WinActive("Google Chrome")
    {
        if WinExist("Visual Studio Code")
            WinActivate("Visual Studio Code")
        else
            Run("C:\Users\taiga\AppData\Local\Programs\Microsoft VS Code\Code.exe")
    }
    else
    {
        if WinExist("Visual Studio Code")
            WinActivate("Visual Studio Code")
        else
            Run("C:\Users\taiga\AppData\Local\Programs\Microsoft VS Code\Code.exe")
    }
}

; ; F13 + X でWindowsターミナルを開く設定
; F13 & x::
; {
;     if WinActive("Ubuntu Windows Terminal")c
;         WinMinimize("Ubuntu Windows Terminal") ; すでにアクティブな場合は背面（最小化）
;     else if WinExist("Ubuntu Windows Terminal")
;         WinActivate ; 開いているがアクティブでない場合はフォーカス
;     else
;         Run("wt.exe") ; 開いていない場合は新しく起動
; }

; F13 & x::
; {
;     if WinActive("Ubuntu Windows Terminal")
;     {
;         if WinExist("Visual Studio Code")
;             WinActivate("Visual Studio Code")
;         else
;             Run("C:\Users\taiga\AppData\Local\Programs\Microsoft VS Code\Code.exe")
;     }
;     else if WinActive("Visual Studio Code")
;     {
;         if WinExist("Ubuntu Windows Terminal")
;             WinActivate("Ubuntu Windows Terminal")
;         else
;             Run("wt.exe")
;     }
;     else
;     {
;         if WinExist("Ubuntu Windows Terminal")
;             WinActivate("Ubuntu Windows Terminal")
;         else
;             Run("wt.exe")
;     }
; }

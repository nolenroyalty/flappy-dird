set curBuf to do shell script "@CWD/flap.py init"
-- We flip to buf2 here so that finder doesn't cache the old filenames in it.
-- This doesn't always work, but more often than not seems to prevent a jarring
-- "show the last frame of the prior game" effect at the start of the next one
tell application "Finder" to set target of front Finder window to ("@CWD/" & "buf2" as POSIX file)
tell application "Finder" to set target of front Finder window to ("@CWD/" & curBuf as POSIX file)
tell application "Finder" to tell front window to update every item

do shell script "@CWD/flap.py await"

set shouldContinue to "continue"
repeat while shouldContinue = "continue"
    tell application "Finder" to set selectedItems to selection
    set curBuf to do shell script "@CWD/flap.py tick " & (number of selectedItems)
    tell application "Finder" to set target of front Finder window to ("@CWD/" & curBuf as POSIX file)
    set shouldContinue to do shell script "@CWD/flap.py sleep"
end repeat

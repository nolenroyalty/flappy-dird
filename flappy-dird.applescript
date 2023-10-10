property projectPath : ""

set myAlias to path to me
set myPath to POSIX path of myAlias -- Converts alias to a Unix style path

-- Find the last occurrence of "/" (slash)
set lastSlash to the offset of "/" in (reverse of characters of myPath) as string

-- Remove the filename from the path
set projectPath to text 1 thru -((lastSlash + 1)) of myPath & "/"

property buf2Path : projectPath & "buf2"
-- A subroutine to set Finder window's target
on setFinderTarget(buf)
    tell application "Finder" to set target of front Finder window to (projectPath & buf as POSIX file)
    tell application "Finder" to tell front window to update every item
end setFinderTarget

-- Main program starts here
set curBuf to do shell script projectPath & "flap.py init"
setFinderTarget("buf2") -- Avoid caching old filenames
setFinderTarget(curBuf)

do shell script projectPath & "flap.py await"

repeat while true -- equivalent to '1 = 1'
    set shouldContinue to "continue"
    repeat while shouldContinue = "continue"
        tell application "Finder" to set selectedItems to selection
        set curBuf to do shell script projectPath & "flap.py tick " & (number of selectedItems)
        setFinderTarget(curBuf)
        set shouldContinue to do shell script projectPath & "flap.py sleep"
    end repeat

    do shell script projectPath & "flap.py await"

    set curBuf to do shell script projectPath & "flap.py init"
    setFinderTarget("buf2") -- Avoid caching old filenames
    setFinderTarget(curBuf)
end repeat

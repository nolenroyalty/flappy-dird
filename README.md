Check out [the blog post](https://eieio.games/nonsense/game-11-flappy-bird-finder/) for lots of details on how this works!

# flappy-dird
An implementation of flappy bird in MacOS's Finder.

To play:
* Clone the repo
* Run `flap.py first-time-setup` (`flap.py` has no dependencies)
* Open Finder and navigate to the directory where you put this code
* Set the display mode to list view
* Open the directory `buf1` and sort the window by "Date Modified", ascending (arrow pointing up). Do the same thing with `buf2`.
    * The game will look really weird if you don't do this!!
* Run `osascript ./flappy-dird.applescript`
* Find the Finder window you opened, play the game.

I will very happily take pull requests if they add new functionality, fix bugs, or are funny.

Gameplay:

https://github.com/nolenroyalty/flappy-dird/assets/1676311/4ba1ecae-0491-4efd-bb06-c6e000b90bf8

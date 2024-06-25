# AIBOMotionWorkbench
This repository contains utilities for AIBO Motion files. To get started, obtain the repo and try out AIBOMotionInfo. 
**It goes without saying that you should not run any script output on a dog unless you want a deadbo on your hands.**

> ## Done: 
>
> - Captured different models in standard poses. You can see the captures in ./poses. This is used as a lookup table to translate AIBOs in poses across models.
>
> - Recognize when keyframes contain known poses (sleep, sit, stand)
>
> ## In progress:
>
> - Get keyframes in known poses and translate PRM codes and joint positions to a specified model in the coresponding pose.
>
> ## Next up:
> 
> - Fix 110 issues, implement end of range limits, interpolate between custom poses.
>

## File info
MotionInfo: Prints info about keyframes

MotionMatcher: Recognizes keyframes in known positions and matches them to the specified model in the coresponding position

MotionHeaderCorrect: Only changes the header so that Skitter will open it

InHousePoseCapture: Captures keyframes 1, 2, and 3 in a known position (sleep, sit, stand) and saves them to a JSON dict to be used for pose matching later

MotionIdent: Finds keyframes that match a known pose without translating PRM codes or saving an updated file

Have fun! 
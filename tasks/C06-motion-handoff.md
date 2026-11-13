# Motion figure handoff for C05 / the data adapter

Kirk requested a gait and motion figure and authorized frontend polishing.

The participant report should show the movement that produced its metrics: a readable body outline with a skeleton toggle, side and front views, separate left/right limbs, a floor reference, play/pause, speed and a keyboard timeline. A synchronized cursor can connect the figure to the supplied hip/knee curves. A selected finding can highlight a region; exact event seeking requires matching event/frame metadata.

The current session contract includes summary metrics and 101-point mean joint curves. It does not include a participant-specific keypoint time series. Mean curves alone cannot reconstruct the original walk. The workplace report's frame data is a side projection and averages left/right leg joints; it must not be reused as a participant's gait.

Proposed handoff, for the contract owner to decide: reference a small replay asset from the session, containing provenance, task and visit identity, fps/timestamps, the 23-point joint order, coordinate axes/units, frames, confidence or explicit gaps, and task/event ranges. Export these from the same accepted synthetic take that produced the displayed results. Keep all flags and clinical thresholds in Python. No invented reference bands or medical body model are needed.

C06 can then implement the viewer against the approved asset without changing metrics. Invalid/missing points should create a visible tracking gap. Default playback should respect reduced motion. Camera controls must not reverse the subject's left and right, including in RTL pages.

The separately prepared workplace prototype has a coordinate-driven body outline, joint highlighting, peak-flexion seeking for the two available frame series, keyboard scrubbing, speed, reduced-motion support, responsive layout and explicit loading/failure states. It is English-only. Port it through the EN/AR catalogs before integrating it into NODAL Screen; preserve all provenance and screening text at the gate.

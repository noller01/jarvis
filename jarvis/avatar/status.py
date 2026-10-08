"""Face as status — thinking / listening / asleep / new content."""

from __future__ import annotations

from enum import Enum

from jarvis.avatar.acting import FacePose


class AvatarStatus(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ASLEEP = "asleep"
    NEW_CONTENT = "new_content"
    CONFIRM = "confirm"


def apply_status(pose: FacePose, status: AvatarStatus, t: float) -> FacePose:
    """Mutate pose toward status-driven targets (look away, eye contact, lids, glance down)."""
    import math

    if status == AvatarStatus.THINKING:
        # looks away while thinking
        pose.head_yaw += (0.35 - pose.head_yaw) * 0.08
        pose.gaze_x += (0.55 - pose.gaze_x) * 0.1
        pose.gaze_y += (0.15 - pose.gaze_y) * 0.08
        pose.brow_l += (0.25 - pose.brow_l) * 0.05
        pose.brow_r += (0.15 - pose.brow_r) * 0.05
    elif status == AvatarStatus.LISTENING:
        # meets your eyes
        pose.head_yaw += (0.0 - pose.head_yaw) * 0.12
        pose.head_pitch += (0.0 - pose.head_pitch) * 0.1
        pose.gaze_x += (0.0 - pose.gaze_x) * 0.15
        pose.gaze_y += (0.0 - pose.gaze_y) * 0.15
        pose.lid_l = max(pose.lid_l, 0.92)
        pose.lid_r = max(pose.lid_r, 0.92)
    elif status == AvatarStatus.ASLEEP:
        # lids fall
        pose.lid_l += (0.05 - pose.lid_l) * 0.06
        pose.lid_r += (0.05 - pose.lid_r) * 0.06
        pose.head_pitch += (0.18 - pose.head_pitch) * 0.04
        pose.gaze_y += (-0.1 - pose.gaze_y) * 0.05
    elif status == AvatarStatus.NEW_CONTENT:
        # glances down at new content
        pose.gaze_y += (0.55 - pose.gaze_y) * 0.12
        pose.head_pitch += (0.22 - pose.head_pitch) * 0.1
    elif status == AvatarStatus.SPEAKING:
        pose.head_yaw += (0.0 - pose.head_yaw) * 0.1
        pose.gaze_x += (0.0 - pose.gaze_x) * 0.08
    elif status == AvatarStatus.CONFIRM:
        pose.brow_l = 0.4
        pose.brow_r = 0.4
        pose.gaze_x = 0.0
        pose.gaze_y = 0.0
    else:
        # idle breathing
        pose.head_pitch += (0.02 * math.sin(t * 1.2) - pose.head_pitch) * 0.05
    return pose

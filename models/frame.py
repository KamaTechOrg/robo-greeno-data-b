from dataclasses import dataclass
import numpy as np


@dataclass
class Frame:
    image: np.ndarray
    timestamp: float
    frame_id: int
    source: str
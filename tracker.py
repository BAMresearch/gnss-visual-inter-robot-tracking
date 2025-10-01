# Copyright (c) 2025 Bundesanstalt für Materialforschung und -prüfung, see LICENSE file
from .baseclasses import Tracker
import cv2 as cv
from logging import getLogger
from datetime import datetime, timezone

logger = getLogger(__name__)

# annotation settings
ANNOTATION_COLOR_PRIMARY = (0, 255, 0)
ANNOTATION_COLOR_SECONDARY = (255, 153, 0)
ANNOTATION_RADIUS = 20
ANNOTATION_THICKNESS = 3

class HueTracker(Tracker):
    """A tracker which only uses HSV hue matching to find the object directly. No track algorithms are used. Target is detected on every frame."""

    def __init__(self, lower_hsv, upper_hsv, min_area):
        self.target_ROI = None
        self.locked = False
        self.lower_hsv = lower_hsv # hue bounds for masking e.g. np.array([100, 150, 50]) 
        self.upper_hsv = upper_hsv # dito
        self.min_area = min_area # minimum area after hue masking for detection

        # telemtry info dict to be added to database via the camera get_measurement function, all data will be interpreted as fields, i.e.
        # do not use static values here. Tracking lock status and angle error are already reported by camera directly. values are tuples with
        # (datetime_timestamp, value, "unit"), e.g. { "best_area": (timestamp, 12.5,"px")}
        self.telemetryinfo = { "best_area": None, "candidates": None}
        
    def start(self):
        self.target_ROI = None
        self.locked = False
   
    def stop(self):
        self.target_ROI = None
        self.locked = False

    def object_position_from_frame(self, frame, annotation_framebuffer = None):
        """Determines the object position in frame in pixels."""
        
        # Convert to HSV color space
        hsv = cv.cvtColor(frame, cv.COLOR_BGR2HSV)

        # Create a mask for the color
        mask = cv.inRange(hsv, self.lower_hsv, self.upper_hsv)

        # Find contours in the mask
        contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

        # find largest contour bigger than min_area
        best_contour = None
        best_area = 0.0
        candidates = 0
        for curr_contour in contours:
            curr_area = cv.contourArea(curr_contour)
            logger.debug(f"found contour with area: {curr_area:.1f}")
            if curr_area > self.min_area:  # Filter small areas
                candidates += 1 # count candidates above threshold
                if curr_area > best_area:
                    best_contour = curr_contour
                    best_area = curr_area
        
        logger.debug(f"best area above threshold: {best_area}")
        # save telemetryinfo for database (inserted via camera class's get_measurement() )
        time = datetime.now(tz=timezone.utc)
        self.telemetryinfo["best_area"] = (time, best_area, "px")
        self.telemetryinfo["candidates"] = (time, candidates, None)
        
        if annotation_framebuffer is not None: # annotate frame with contours
                cv.drawContours(annotation_framebuffer, contours, -1, ANNOTATION_COLOR_SECONDARY, ANNOTATION_THICKNESS)
        
        if best_contour is not None:
            self.locked = True
            x, y, w, h = cv.boundingRect(best_contour)
            # calculate position and return
            pos_x = (x+w/2)
            pos_y = (y+h/2)
            if annotation_framebuffer is not None: # annotate frame with target
                cv.circle(annotation_framebuffer, (int(pos_x), int(pos_y)), ANNOTATION_RADIUS, ANNOTATION_COLOR_PRIMARY, ANNOTATION_THICKNESS)
            return pos_x, pos_y
        else: # target not found            
            self.locked = False
            return None, None

            
class DummyTrackerNone(Tracker):
    """A tracker which never detects anything and immediately returns. Used for speed/delay testing/debugging."""

    def __init__(self):
        self.locked = False
    
    def start(self):
        pass
   
    def stop(self):
        pass

    def object_position_from_frame(self, frame, annotation_framebuffer = None):        
        return None, None

class DummyTrackerMiddle(Tracker):
    """A tracker that always immediately detects object in the middle of frame. Used for speed/delay testing/debugging."""

    def __init__(self):
        self.locked = True
    
    def start(self):
        pass
   
    def stop(self):
        pass

    def object_position_from_frame(self, frame, annotation_framebuffer = None):        
        frameheight, framewidth, _ = frame.shape
        if annotation_framebuffer is not None: # annotate frame
            cv.circle(annotation_framebuffer, (int(framewidth/2), int(frameheight/2)), ANNOTATION_RADIUS, ANNOTATION_COLOR_PRIMARY, ANNOTATION_THICKNESS)
        return framewidth/2, frameheight/2
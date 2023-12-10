import threading

# audio libraries
# be sure to import threading libraries prior to these imports
# as the subprocess behavior will be different
from pydub import AudioSegment
from pydub.playback import play

class ScootSound:
    """
    Class to manage and play different audio effects for the scooter.

    Attributes:
        sound_meltdown (AudioSegment): An audio segment for the 'meltdown' mode.
        sound_disco (AudioSegment): An audio segment for the 'disco' mode.
        sound_underlight (AudioSegment): An audio segment for the 'underlight' mode.
        sound_fireplace (AudioSegment): An audio segment for the 'fireplace' mode.
        sound_lights_out (AudioSegment): An audio segment for the 'lights out' mode.

    Depencencies:
        threading
        pydub

    :param enabled: bool: Enable audio output.
    """
    def __init__(self, enabled: bool = True):
        """
        Initializes the ScootSound class with empty audio segments.
        """
        self.enabled = enabled
        self.sound_meltdown = AudioSegment.empty()
        self.sound_disco = AudioSegment.empty()
        self.sound_underlight = AudioSegment.empty()
        self.sound_fireplace = AudioSegment.empty()
        self.sound_lights_out = AudioSegment.empty()

    def import_from_disk(self):
        """
        Imports audio files from the disk into their corresponding attributes.
        Assumes the existence of MP3 files in the 'static/sounds/' directory.
        This method blocks while reading and parsing audio, which may be lengthy.
        """
        if self.enabled:
            self.sound_meltdown = AudioSegment.from_mp3("static/sounds/meltdown.mp3")
            self.sound_disco = AudioSegment.from_mp3("static/sounds/disco.mp3")
            self.sound_underlight = AudioSegment.from_mp3("static/sounds/underlight.mp3")
            self.sound_fireplace = AudioSegment.from_mp3("static/sounds/fireplace.mp3")
            self.sound_energyweapon = AudioSegment.from_mp3("static/sounds/energyweapon.mp3")
            self.sound_lights_out = AudioSegment.from_mp3("static/sounds/lights-out.mp3")

    def play(self, segment: AudioSegment) -> threading.Thread:
        """
        Plays an audio segment in a new daemon thread.

        :param segment (AudioSegment): The audio segment to be played.
        :return threading.Thread: The thread in which the audio segment is being played.
        """
        thread = threading.Thread()
        if self.enabled:
            thread = threading.Thread(target = lambda: play(segment), daemon = True)
        else:
            thread = threading.Thread(target = lambda: None)
        thread.start()
        return thread
import os
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl


class SoundPlayer:
    def __init__(self, sound_file="correct-chime.mp3"):
        # Inicializa o player de mídia para alertas sonoros
        self.player = QMediaPlayer()
        sound_file_path = os.path.join(os.path.dirname(__file__), "assets/sounds", sound_file)
        if os.path.exists(sound_file_path):
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(sound_file_path)))
        else:
            print(f"Arquivo de som não encontrado: {sound_file_path}")
        self.player.setVolume(100)  # Ajuste o volume conforme necessário

    def play_sound(self):
        """Reproduz um som de alerta."""
        if self.player.mediaStatus() == QMediaPlayer.NoMedia:
            print("Nenhum arquivo de mídia carregado para o player.")
            return
        self.player.stop()
        self.player.play()

import os
import sqlite3
import sys
import random

from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QUrl, QEventLoop, QSize, QTime
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QFileDialog, QAbstractItemView

from ui_file import Ui_MainWindow # Загружаем интерфейс из сгенерированного файла


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("Icons/soundPadIcon.ico"))

        self.player = QMediaPlayer() # Инициализация медиа плеера
        self.output = QAudioOutput()
        self.player.setAudioOutput(self.output)
        self.sounds_paths = []
        self.last_volume = 0
        self.muted = False
        self.counter_value = 0
        self.wait_key = False
        self.media_devices = QMediaDevices()

        self.setupUi(self)

        # Запрещаем вручную менять таблицу
        self.tableWidget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # При выделении одной колонки выделяется сразу весь ряд
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tableWidget.setSortingEnabled(True)
        self.progressTimeEdit.setReadOnly(True)

        self.connectDB()
        self.playCounter()
        self.getDevices()

        # Иконки на кнопки
        self.reproductionButton.setIcon(QIcon("Icons/startIcon.png"))
        self.reproductionButton.setIconSize(QSize(32, 32))
        self.suspend_resumeButton.setIcon(QIcon("Icons/pauseIcon.png"))
        self.suspend_resumeButton.setIconSize(QSize(32, 32))
        self.stopButton.setIcon(QIcon("Icons/stopIcon.png"))
        self.stopButton.setIconSize(QSize(32, 32))
        self.muteButton.setIcon(QIcon("Icons/muteIcon.png"))
        self.muteButton.setIconSize(QSize(32, 32))

        # Коннекты
        self.addSound.triggered.connect(self.add)
        self.deleteButton.clicked.connect(self.delete)
        self.reproductionButton.clicked.connect(self.reproduction)
        self.reproductionRandom.triggered.connect(self.reproduction_random)
        self.volumeSlider.sliderMoved.connect(self.changeVolume)
        self.volumeSlider.actionTriggered.connect(self.changeVolume)
        self.muteButton.clicked.connect(self.mute)
        self.progressSlider.sliderMoved.connect(self.changePosition)
        self.player.positionChanged.connect(self.changeProgress)
        self.player.durationChanged.connect(self.changeDuration)
        self.stopButton.clicked.connect(self.playerStop)
        self.suspend_resumeButton.clicked.connect(self.playerPause_resume)
        self.reproduction_cur.triggered.connect(self.reproduction)
        self.reproduction_device.currentIndexChanged.connect(self.changeDevice)
        self.stop.triggered.connect(self.playerStop)
        self.pause_resume.triggered.connect(self.playerPause_resume)
        self.exit.triggered.connect(lambda: sys.exit(0)) # Выключение можно сделать лямбдой
        self.tableWidget.cellClicked.connect(self.changeCurrentTrack)
        self.tableWidget.cellDoubleClicked.connect(self.changeAndPlay)
        self.addKey.triggered.connect(self.addHotkey)
        self.deleteKey.triggered.connect(self.DeleteKey)
        self.repeat_current.stateChanged.connect(self.repeat_cur)
        self.repeat_list.stateChanged.connect(self.repeat_next)
        self.media_devices.audioOutputsChanged.connect(self.getDevices)

    def connectDB(self):
        '''Подключаем базу данных и считываем все звуки из нее'''
        self.con = sqlite3.connect("sounds_db.sqlite")
        self.cur = self.con.cursor()

        self.hotkeys = self.cur.execute("""SELECT id, hotkey
        FROM hotkeys""").fetchall()
        self.sounds = self.cur.execute("""SELECT id, name, duration, hotkey, path
        FROM sounds""").fetchall()
        self.tableWidget.setRowCount(len(self.sounds))

        for row, sound in enumerate(self.sounds):
            self.sounds_paths.append(sound[4])

            for column, val in enumerate(sound[:3]):
                if column == 2: # Для длины там отдельная история
                    item = QTableWidgetItem(f"{sound[2] // 60}:{sound[2] % 60:02d}")
                else:
                    item = QTableWidgetItem(str(val))
                item.setData(Qt.ItemDataRole.UserRole, sound[4])
                self.tableWidget.setItem(row, column, item)
            self.tableWidget.setItem(row, 3, QTableWidgetItem(dict(self.hotkeys).get(sound[3], "NONE")))

        self.tableWidget.resizeColumnsToContents()
        self.tableWidget.resizeRowsToContents()

        self.numberOfSounds.setText(str(self.tableWidget.rowCount()))

    def add(self):
        '''Загружаем файл и добавляем его в таблицу и в БД'''
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать аудио файл", "",
            "Аудио (*.mov *.mp4 *.mp3);; Все файлы (*)"
        )

        if file_path:
            self.player.setSource(QUrl.fromLocalFile(file_path)) # Загружаем в плеер текущий файл
            loop = QEventLoop() # создаем локальный процесс чтобы вычислить длину загруженного файла
            self.player.durationChanged.connect(loop.quit) # Когда длина определяется завершаем локальный процесс
            self.player.errorOccurred.connect(loop.quit) # И если этот файл нельзя прочитать
            loop.exec()
            self.player.durationChanged.disconnect(loop.quit)
            self.player.errorOccurred.disconnect(loop.quit)
            if self.player.error() != QMediaPlayer.Error.NoError:
                return

            # Убираем расширение файла, [:-1] - срез с начала до предпоследнего элемента
            base_name = "".join(os.path.basename(file_path).split(".")[:-1])  # join собрал срез в одну строку
            self.tableWidget.setRowCount(self.tableWidget.rowCount() + 1)
            self.tableWidget.setItem(self.tableWidget.rowCount() - 1, 3, QTableWidgetItem("NONE"))
            # Изначально нет клавиши
            self.tableWidget.setItem(self.tableWidget.rowCount() - 1, 2, QTableWidgetItem(
                f"{self.player.duration() // 1000 // 60}:{self.player.duration() // 1000 % 60:02d}"))
            self.tableWidget.setItem(self.tableWidget.rowCount() - 1, 1, QTableWidgetItem(base_name))
            item = QTableWidgetItem(str(self.tableWidget.rowCount()))
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.tableWidget.setItem(self.tableWidget.rowCount() - 1, 0, item)
            self.tableWidget.resizeColumnsToContents()
            self.tableWidget.resizeRowsToContents()

            self.cur.execute("""INSERT INTO sounds(id, name, path, duration) VALUES(?, ?, ?, ?)""",
                             (self.tableWidget.rowCount(), base_name, file_path, self.player.duration() // 1000))
            self.con.commit()

            self.sounds_paths.append(file_path)

            self.numberOfSounds.setText(str(self.tableWidget.rowCount()))

    def delete(self):
        '''Очищаем таблицу и БД'''
        self.tableWidget.clear() # Очищаем полностью таблицу (заголовки колонок стриаются)
        # Вручную возращаем их
        self.tableWidget.setHorizontalHeaderLabels(["Номер", "Название", "Длительность", "Клавиша"])
        self.tableWidget.setRowCount(0)

        self.cur.execute("""DELETE FROM sounds""") # Очищаем БД
        self.cur.execute("""DELETE FROM hotkeys""")
        self.con.commit()

        self.player.setSource(QUrl("")) # Очищаем плеер

        self.sounds_paths = []
        self.sounds = []
        self.counter_value = 0

        self.numberOfSounds.setText("0")
        self.counter.setText("0")

    def reproduction(self):
        try:
            self.player.stop() # Останавливаем что играло до этого
            self.player.play()

            self.counter_value += 1
            self.playCounter()
        except Exception:
            pass

    def reproduction_random(self):
        try:
            self.player.setSource(QUrl.fromLocalFile(random.choice(self.sounds_paths)))
            self.reproduction()
        except Exception:
            pass

    def changeVolume(self):
        if not self.muted:
            if self.volumeSlider.value() < 10:
                volume = 0.0
            else:
                volume = self.volumeSlider.value() / 1000
            self.output.setVolume(volume)

        self.volume.setText(f"{self.volumeSlider.value() // 10}%")
        self.last_volume = self.volumeSlider.value() / 1000

    def mute(self):
        if self.muted:
            self.output.setVolume(self.last_volume)
            self.last_volume = 0
            self.muted = False
        else:
            self.last_volume = self.volumeSlider.value() / 1000
            self.output.setVolume(0.0)
            self.muted = True

    def changeDuration(self):
        self.progressSlider.setRange(0, self.player.duration())

    def changeProgress(self):
        if not self.progressSlider.isSliderDown():
            self.progressSlider.setValue(self.player.position())
        self.progressTimeEdit.setTime(QTime(int(
            self.player.position() / 1000 // 60
        ), int(
            self.player.position() / 1000 % 60
        )))

    def changePosition(self):
        self.player.setPosition(self.progressSlider.value())

    def playerStop(self):
        self.player.stop()

    def playerPause_resume(self):
        if self.player.isPlaying():
            self.player.pause()
        else:
            self.reproduction()

    def playCounter(self):
        self.counter.setText(str(self.counter_value))

    def getDevices(self):
        self.reproduction_device.blockSignals(True)
        self.reproduction_device.clear()
        for i, device in enumerate(self.media_devices.audioOutputs()):
            self.reproduction_device.addItem(device.description(), device)
        self.reproduction_device.blockSignals(False)
        self.changeDevice(self.reproduction_device.currentIndex())

    def changeDevice(self, index): # Функция принимает индекс элемента в комбобоксе
        self.output.setDevice(self.reproduction_device.itemData(index))

    def changeCurrentTrack(self, row, col): # Функция принимает row и column той клетки, на которую кликнули
        self.player.setSource(QUrl.fromLocalFile(self.tableWidget.item(row, 0).data(Qt.ItemDataRole.UserRole)))

    def changeAndPlay(self, row, col):
        self.changeCurrentTrack(row, col)
        self.reproduction()

    def addHotkey(self):
        if self.player.source().isEmpty():
            return
        self.wait_key = True

    def keyPressEvent(self, event):
        if event.text() in [i[1] for i in self.hotkeys]:
            try:
                for row in range(self.tableWidget.rowCount()):
                    if event.text() == self.tableWidget.item(row, 3).text():
                        self.changeAndPlay(row, 3)
            except Exception as e:
                print(e)
        if self.wait_key:
            self.wait_key = False
            if any(event.text() == h[1] for h in self.hotkeys):
                return # Одну клавишу двум трекам не назначишь
            file_path = self.player.source().path()[1:] # Возращает путь формата /C:/... поэтому первый "/" срезаем
            next_id = self.cur.execute("""SELECT MAX(id) FROM hotkeys""").fetchone()[0]
            next_id = next_id + 1 if next_id else 1
            self.cur.execute("""INSERT INTO hotkeys(id, hotkey) VALUES(?, ?)""", (next_id, event.text()))
            self.cur.execute("""UPDATE sounds SET hotkey = ? WHERE path = ?""", (next_id, file_path))
            self.con.commit()
            self.hotkeys.append((next_id, event.text()))

            for row in range(self.tableWidget.rowCount()):
                if self.tableWidget.item(row, 0).data(Qt.ItemDataRole.UserRole) == file_path:
                    self.tableWidget.item(row, 3).setText(event.text())

    def DeleteKey(self):
        if self.hotkeys:
            hotkey = None
            file_path = self.player.source().path()[1:]
            for row in range(self.tableWidget.rowCount()):
                if self.tableWidget.item(row, 0).data(Qt.ItemDataRole.UserRole) == file_path:
                    hotkey = self.tableWidget.item(row, 3).text()
                    self.tableWidget.item(row, 3).setText("NONE")

            self.cur.execute("""DELETE FROM hotkeys WHERE hotkey = ?""", (hotkey,))
            self.cur.execute("""UPDATE sounds SET hotkey = NULL WHERE path = ?""", (file_path,))
            self.con.commit()

            self.hotkeys = [i for i in self.hotkeys if i[1] != hotkey]

    def repeat_cur(self):
        try:
            if self.repeat_current.isChecked():
                self.repeat_list.setChecked(False)
                self.player.mediaStatusChanged.connect(self.reproductionRepeat)
                self.player.mediaStatusChanged.disconnect(self.playNext)
            else:
                self.player.mediaStatusChanged.disconnect(self.reproductionRepeat)
        except Exception:
            pass

    def reproductionRepeat(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.reproduction()

    def repeat_next(self):
        try:
            if self.repeat_list.isChecked():
                self.repeat_current.setChecked(False) # Включен либо тот либо тот
                self.player.mediaStatusChanged.connect(self.playNext)
                self.player.mediaStatusChanged.disconnect(self.reproductionRepeat)
            else:
                self.player.mediaStatusChanged.disconnect(self.playNext)
        except Exception:
            pass

    def playNext(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            file_path = self.player.source().path()[1:]
            for row in range(self.tableWidget.rowCount()):
                if file_path == self.tableWidget.item(row, 0).data(Qt.ItemDataRole.UserRole):
                    if row == self.tableWidget.rowCount() - 1:
                        self.changeAndPlay(0, 0)
                    else:
                        self.changeAndPlay(row + 1, 0)


if __name__ == '__main__':
    # Запуск приложения
    app = QApplication(sys.argv)
    ex = MainWindow()
    ex.show()
    sys.exit(app.exec())

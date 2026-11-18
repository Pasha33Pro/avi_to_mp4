import os
import sys
import subprocess
import threading
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Drone AVI to MP4 (yuvj422p Fix)")
        self.root.geometry("550x480")
        self.root.resizable(False, False)

        self.files_to_convert = []
        self.target_dir = ""
        self.is_converting = False

        self._build_ui()
        self._check_ffmpeg()

    def _build_ui(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        self.btn_select = ttk.Button(top_frame, text="📁 Выбрать AVI", command=self.select_files)
        self.btn_select.pack(side=tk.LEFT, padx=5)

        self.btn_open_folder = ttk.Button(top_frame, text="📂 Папка результата", command=self.open_target_folder,
                                          state=tk.DISABLED)
        self.btn_open_folder.pack(side=tk.RIGHT, padx=5)

        self.lbl_folder = ttk.Label(self.root, text="Папка сохранения: не выбрана", foreground="gray")
        self.lbl_folder.pack(pady=(0, 10))

        progress_frame = ttk.Frame(self.root, padding="10")
        progress_frame.pack(fill=tk.X, padx=10)

        ttk.Label(progress_frame, text="Общий прогресс:").pack(anchor=tk.W)
        self.progress_overall = ttk.Progressbar(progress_frame, orient="horizontal", length=500, mode="determinate")
        self.progress_overall.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(progress_frame, text="Текущий файл:").pack(anchor=tk.W)
        self.progress_current = ttk.Progressbar(progress_frame, orient="horizontal", length=500, mode="determinate")
        self.progress_current.pack(fill=tk.X, pady=(0, 5))

        self.lbl_status = ttk.Label(self.root, text="Статус: Ожидание...", font=("Arial", 10, "bold"))
        self.lbl_status.pack(pady=5)

        self.log_text = tk.Text(self.root, height=8, state=tk.DISABLED, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, padx=10, pady=5)

        log_btn_frame = ttk.Frame(self.root)
        log_btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_copy = ttk.Button(log_btn_frame, text="📋 Скопировать лог", command=self.copy_log)
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        self.btn_start = ttk.Button(self.root, text="🚀 Начать конвертацию", command=self.start_conversion,
                                    state=tk.DISABLED)
        self.btn_start.pack(pady=10)

    def _check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            self._log("✅ FFmpeg найден.")
        except (FileNotFoundError, subprocess.CalledProcessError):
            self._log("❌ ОШИБКА: FFmpeg не найден! Добавьте в PATH.")
            messagebox.showerror("Ошибка", "FFmpeg не установлен.")
            self.btn_start.config(state=tk.DISABLED)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите AVI файлы с дрона",
            filetypes=[("Видео AVI", "*.avi")]
        )
        if files:
            self.files_to_convert = list(files)
            base_dir = os.path.dirname(self.files_to_convert[0])
            self.target_dir = os.path.join(base_dir, "convertedVideoDrone")
            os.makedirs(self.target_dir, exist_ok=True)

            self.lbl_folder.config(text=f"💾 Сохранение в: {self.target_dir}")
            self.btn_start.config(state=tk.NORMAL)
            self._log(f"📁 Выбрано файлов: {len(self.files_to_convert)}")
            self._log("🔧 Режим: Исправление yuvj422p -> yuv420p (для телефонов)")
            self.progress_overall['maximum'] = len(self.files_to_convert)
            self.progress_overall['value'] = 0

    def start_conversion(self):
        if not self.files_to_convert or self.is_converting:
            return

        # Удаляем старые файлы, чтобы не было пропуска
        self._log("🧹 Очистка старых файлов в папке результата...")
        for file_path in self.files_to_convert:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            old_output = os.path.join(self.target_dir, f"{base_name}.mp4")
            if os.path.exists(old_output):
                try:
                    os.remove(old_output)
                except Exception:
                    pass

        self.is_converting = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_select.config(state=tk.DISABLED)
        self._log("🔄 Начало конвертации...")

        thread = threading.Thread(target=self._conversion_worker, daemon=True)
        thread.start()

    def _conversion_worker(self):
        success_count = 0
        error_count = 0

        for index, file_path in enumerate(self.files_to_convert):
            filename = os.path.basename(file_path)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(self.target_dir, f"{base_name}.mp4")

            self._update_status(f"Конвертация: {filename} ({index + 1}/{len(self.files_to_convert)})")
            self._log(f"🎬 Обработка: {filename}")

            duration = self._get_duration(file_path)

            # 🚀 СПЕЦИАЛЬНАЯ КОМАНДА ПОД ДИАГНОСТИКУ (yuvj422p + pcm_s16le)
            cmd = [
                "ffmpeg",
                "-fflags", "+genpts",  # 1. Исправляем метки времени
                "-i", file_path,
                "-c:v", "libx264",
                "-profile:v", "baseline",  # 2. Максимальная совместимость
                "-level", "3.0",
                "-pix_fmt", "yuv420p",  # 3. ГЛАВНОЕ: Принудительно меняем yuvj422p на yuv420p
                "-vf", "format=yuv420p,fps=30,scale=640:480",  # 4. Жестко задаем формат, 30 FPS и точное разрешение
                "-r", "30",  # 5. Фиксируем частоту кадров на выходе
                "-an",  # 6. Полностью вырезаем сырой pcm_s16le звук
                "-movflags", "+faststart",  # 7. Оптимизация для мобильных
                "-y", output_path
            ]

            try:
                process = subprocess.Popen(
                    cmd,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='ignore'
                )

                for line in process.stderr:
                    if 'time=' in line:
                        match = re.search(r'time=([\d:.]+)', line)
                        if match and duration:
                            current_time = self._parse_time(match.group(1))
                            percent = min(100, int((current_time / duration) * 100))
                            self._update_current_progress(percent)

                process.wait()

                if process.returncode == 0:
                    self._log(f"✅ Успешно: {base_name}.mp4")
                    success_count += 1
                else:
                    self._log(f"❌ Ошибка ffmpeg: {filename}")
                    error_count += 1

            except Exception as e:
                self._log(f"💥 Исключение: {filename} -> {e}")
                error_count += 1

            self._update_progress(index + 1, 100)

        self.is_converting = False
        self.root.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_select.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_open_folder.config(state=tk.NORMAL))
        self._update_status(f"🏁 Готово! Успешно: {success_count}, Ошибок: {error_count}")
        self._log(f"🏁 Конвертация завершена. Можно проверять на телефоне!")
        messagebox.showinfo("Готово",
                            f"Конвертация завершена!\nУспешно: {success_count}\nОшибок: {error_count}\n\nТеперь видео должно открыться на телефоне!")

    def _get_duration(self, file_path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                   "default=noprint_wrappers=1:nokey=1", file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 60.0  # Заглушка, если не удалось получить длительность

    def _parse_time(self, time_str):
        parts = time_str.split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(parts[0])

    def _update_status(self, text):
        self.root.after(0, lambda: self.lbl_status.config(text=text))

    def _update_progress(self, overall_value, current_value):
        self.root.after(0, lambda: self.progress_overall.config(value=overall_value))
        self.root.after(0, lambda: self.progress_current.config(value=current_value))

    def _update_current_progress(self, percent):
        self.root.after(0, lambda: self.progress_current.config(value=percent))

    def _log(self, message):
        def append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

        self.root.after(0, append)

    def copy_log(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.log_text.get("1.0", tk.END))
            self._log("✅ Лог скопирован в буфер обмена!")
        except Exception as e:
            self._log(f"❌ Ошибка: {e}")

    def open_target_folder(self):
        if self.target_dir and os.path.exists(self.target_dir):
            if sys.platform == "win32":
                os.startfile(self.target_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", self.target_dir])
            else:
                subprocess.run(["xdg-open", self.target_dir])


if __name__ == "__main__":
    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()
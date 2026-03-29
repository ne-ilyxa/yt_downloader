import yt_dlp
import os
import ssl
from pathlib import Path
import sys
from get_info import *
import random 
import platform

print("Убедись, что запущен zapret-discord-youtube > general(FAKE TLS AUTO ALT)")

# Отключаем проверку SSL
# ssl._create_default_https_context = ssl._create_unverified_context

def download_format(url, format_id, headers, convert_to_mp3, output_path="downloads", merge_formats=None):
    """Скачивает выбранный формат"""
    Path(output_path).mkdir(exist_ok=True)

    is_video_audio_merge = '+' in str(format_id)

    def build_ydl_opts(merge_output_format=None):
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(output_path, '%(title).100s.%(ext)s'),

            'remote_components': ['ejs:github'],

            # Упрощаем заголовки (убираем излишнее)
            'user_agent': headers['User-Agent'],
            'http_headers': headers,

            # Базовые параметры загрузки
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,

            # Добавляем cookies если есть
            'cookiefile': 'exported-cookies.txt' if os.path.exists('exported-cookies.txt') else None,
        }

        if platform.system() != 'Linux':
            ydl_opts['js_runtimes'] = {
                'quickjs': {
                    'path': QUICKJS_PATH
                }
            }

        # Конвертация в MP3 разрешена только для чистого аудио
        if convert_to_mp3 and not is_video_audio_merge:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        # Настройки объединения видео+аудио
        if is_video_audio_merge and merge_output_format:
            ydl_opts['merge_output_format'] = merge_output_format

        return ydl_opts

    # Для video+audio делаем попытку MP4, при проблемах — fallback в MKV
    if is_video_audio_merge:
        if merge_formats:
            merge_attempts = [(fmt, fmt.upper()) for fmt in merge_formats]
        else:
            merge_attempts = [('mp4', 'MP4'), ('mkv', 'MKV')]
    else:
        merge_attempts = [(None, None)]

    last_error = None
    for merge_fmt, merge_label in merge_attempts:
        try:
            with yt_dlp.YoutubeDL(build_ydl_opts(merge_output_format=merge_fmt)) as ydl:
                if is_video_audio_merge:
                    print(f"📥 Скачивание и объединение (в {merge_label}) форматов: {format_id}...")
                else:
                    print(f"📥 Скачивание формата ID: {format_id}...")
                ydl.download([url])
                print("✅ Загрузка завершена!")
                return True
        except Exception as e:
            last_error = e
            if not is_video_audio_merge:
                break
            if merge_fmt == 'mp4':
                print(f"⚠️ Не удалось объединить в MP4: {e}")
                print("🔁 Пробуем объединение в MKV...")
            else:
                break

    print(f"❌ Ошибка при скачивании: {last_error}")
    return False

def main():
    print("=== YouTube Downloader ===")
    test_connection()
    while True:
        url = input("\n🎬 Введите URL YouTube видео (или 'quit' для выхода): ").strip()
        # if (url == ""):
        #   url = "https://www.youtube.com/watch?v=HpyVBF03vI8"
        if url.lower() in ['quit', 'exit', 'q']:
            break
            
        if not url.startswith(('http://', 'https://')):
            print("❌ Пожалуйста, введите корректный URL")
            continue
        
        headers = get_realistic_headers()
        
        info = get_video_info(url, headers)
            
        if not info:
            print("❌ Не удалось получить информацию о видео")
            continue
        
        # Получаем и показываем форматы
        audio_formats, video_formats, combined_formats = list_formats(info)
        all_formats = display_formats(audio_formats, video_formats, combined_formats)
        
        if not all_formats:
            print("❌ Нет доступных форматов для скачивания")
            continue
        
        # Выбор формата
        try:
            choice = input(f"\n🎯 Выберите номер формата (1-{len(all_formats)}) или Enter для лучшего аудио: ").strip()
            
            if choice == '':
                # Автоматически выбираем лучший аудио формат
                format_type, selected_format = None, None
                
                # Ищем лучший аудио (по битрейту)
                for fmt_type, fmt_info in all_formats:
                    if fmt_type == 'audio':
                        if not selected_format or fmt_info['abr'] > selected_format['abr']:
                            selected_format = fmt_info
                            format_type = fmt_type
                
                if not selected_format:
                    print("⚠️ Аудио форматы не найдены, используем первый доступный")
                    format_type, selected_format = all_formats[0]
                
                format_id = selected_format['id']
                print(f"🎵 Автоматически выбран: ID {format_id} ({selected_format['abr']}kbps)")
                
            elif choice.isdigit() and 1 <= int(choice) <= len(all_formats):
                # Находим выбранный формат
                selected_format = None
                format_type = None
                
                for fmt_type, fmt_info in all_formats:
                    if fmt_info['display_id'] == int(choice):
                        selected_format = fmt_info
                        format_type = fmt_type
                        break
                
                if selected_format:
                    format_id = selected_format['id']
                    print(f"✅ Выбран формат: ID {format_id}")
                else:
                    print("⚠️ Формат не найден, используем лучший аудио")
                    format_id = 'bestaudio'
            else:
                print("⚠️ Неверный выбор, используем лучший аудио")
                format_id = 'bestaudio'

            merge_formats = None

            # Если выбран формат "только видео", автоматически подбираем аудио и объединяем
            if format_type == 'video' and selected_format:
                def pick_best_audio(formats, prefer_m4a=False):
                    if not formats:
                        return None
                    candidates = formats
                    if prefer_m4a:
                        m4a = [f for f in formats if (f.get('ext') or '').lower() == 'm4a']
                        if m4a:
                            candidates = m4a
                    return max(candidates, key=lambda f: (f.get('abr') or 0))

                video_ext = (selected_format.get('ext') or '').lower()
                # Если выбрано MP4-видео — берем m4a (AAC) чтобы MP4 точно был со звуком
                prefer_m4a = video_ext == 'mp4'
                best_audio = pick_best_audio(audio_formats, prefer_m4a=prefer_m4a)
                if best_audio:
                    video_id = selected_format['id']
                    audio_id = best_audio['id']
                    format_id = f"{video_id}+{audio_id}"
                    audio_ext = (best_audio.get('ext') or '').lower()

                    # Выбор контейнера для merge:
                    # - mp4+ m4a -> mp4
                    # - иначе сразу mkv (чтобы не получить mp4 без звука у некоторых плееров)
                    if video_ext == 'mp4' and audio_ext == 'm4a':
                        merge_formats = ['mp4', 'mkv']
                        merge_note = "MP4 (fallback в MKV при несовместимости)"
                    else:
                        merge_formats = ['mkv']
                        merge_note = "MKV (чтобы гарантировать воспроизведение звука)"

                    print(
                        f"🎬 Выбрано видео ID {video_id} ({video_ext or 'n/a'}); "
                        f"автоматически выбрано аудио ID {audio_id} ({best_audio.get('abr', 0)}kbps, {audio_ext or 'n/a'})."
                    )
                    print(f"🔧 Будет выполнено объединение в {merge_note}.")
                else:
                    print("⚠️ Аудио форматы не найдены — скачиваю только видео без объединения.")
            
            # Конвертация в MP3 только для аудио-форматов; видео оставляем как есть
            convert_to_mp3 = False
            if format_type == 'audio':
                convert_option = input("🎵 Конвертировать в MP3? (y/N): ").strip().lower()
                convert_to_mp3 = convert_option == 'y' or convert_option == ""
            
            # Скачиваем
            download_format(url, format_id, headers, convert_to_mp3, merge_formats=merge_formats)
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("Попробуйте другой формат или видео")

if __name__ == "__main__":
    main()
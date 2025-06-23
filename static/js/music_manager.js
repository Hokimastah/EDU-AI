// static/js/music_manager.js

document.addEventListener('DOMContentLoaded', () => {
    // Fungsi untuk mencari elemen audio di halaman saat ini
    const getCurrentAudioElement = () => {
        // Prioritaskan musik game jika ada, jika tidak, cari musik menu
        return document.getElementById('game-music') || document.getElementById('menu-music');
    };

    // Fungsi untuk menghentikan SEMUA musik yang mungkin sedang bermain
    const stopAllMusic = () => {
        document.querySelectorAll('audio').forEach(audio => {
            audio.pause();
        });
    };

    // Fungsi untuk memainkan musik yang benar untuk halaman ini
    const playCorrectMusic = () => {
        const currentAudio = getCurrentAudioElement();
        if (!currentAudio) return; // Jika tidak ada elemen audio di halaman ini, berhenti

        // Ambil status musik terakhir dari memori browser
        const musicState = JSON.parse(localStorage.getItem('musicState'));

        // Jika musik yang seharusnya diputar SAMA dengan yang ada di halaman ini
        if (musicState && musicState.src === currentAudio.src) {
            currentAudio.currentTime = musicState.time; // Lanjutkan dari waktu terakhir
            if (musicState.isPlaying) {
                currentAudio.play().catch(e => console.log("Autoplay dicegah, tunggu interaksi pengguna."));
            }
        } else {
            // Jika musiknya berbeda (misal, dari menu ke game), mulai dari awal
            stopAllMusic();
            currentAudio.play().catch(e => console.log("Autoplay dicegah, tunggu interaksi pengguna."));
        }
    };

    // --- LOGIKA UTAMA ---

    // 1. Coba mainkan musik yang benar saat halaman dimuat
    playCorrectMusic();

    // 2. Simpan status musik ke memori setiap detik
    setInterval(() => {
        const currentAudio = getCurrentAudioElement();
        if (currentAudio && !currentAudio.paused) {
            const state = {
                src: currentAudio.src,
                time: currentAudio.currentTime,
                isPlaying: true
            };
            localStorage.setItem('musicState', JSON.stringify(state));
        }
    }, 1000);

    // 3. Pastikan musik bisa diputar setelah interaksi pengguna pertama (kebijakan browser)
    document.body.addEventListener('click', () => {
        const currentAudio = getCurrentAudioElement();
        if (currentAudio && currentAudio.paused) {
            // Cek kembali memori jika musik seharusnya sudah bermain
            const musicState = JSON.parse(localStorage.getItem('musicState'));
            if (musicState && musicState.src === currentAudio.src && musicState.isPlaying) {
                currentAudio.play();
            }
        }
    }, { once: true });
});

// Menunggu seluruh halaman HTML dimuat sebelum menjalankan skrip
document.addEventListener('DOMContentLoaded', () => {

    // Mengambil elemen-elemen dari HTML
    const questionContainer = document.getElementById('question-container');
    const optionsContainer = document.getElementById('options-container');
    const feedbackContainer = document.getElementById('feedback-container');
    const scoreValueElement = document.getElementById('score-value');
    const mascotImg = document.getElementById('mascot-oli');
    const gameMusic = document.getElementById('game-music');
    const clickSound = document.getElementById('click-sound');

    // --- VARIABEL STATUS GAME ---
    const gameBody = document.querySelector('body');
    const currentTopic = gameBody.dataset.topic;
    const currentProfileId = gameBody.dataset.profileId;
    let currentScore = 0;

    // --- FUNGSI-FUNGSI LOGIKA GAME ---
    
    // PERUBAHAN DI SINI: Fungsi baru untuk mengambil skor awal
    async function fetchInitialScore() {
        try {
            const response = await fetch('/get-initial-score', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: currentTopic }),
            });
            if (!response.ok) {
                throw new Error('Gagal mengambil skor awal.');
            }
            const data = await response.json();
            if (data.initial_score !== undefined) {
                currentScore = data.initial_score;
                scoreValueElement.textContent = currentScore;
            }
        } catch (error) {
            console.error('Error fetching initial score:', error);
            // Jika gagal, biarkan skor tetap 0
            scoreValueElement.textContent = 0;
        }
    }

    function getLevelFromScore(score) {
        if (score < 20) return 'mudah';
        else if (score < 50) return 'sedang';
        else if (score < 100) return 'sulit';
        else if (score < 200) return 'sangat sulit';
        else return 'ekstrim';
    }

    async function fetchQuestion() {
        feedbackContainer.textContent = '';
        feedbackContainer.className = 'feedback-box';
        optionsContainer.innerHTML = '<p>Oli sedang membuat soal...</p>';

        const level = getLevelFromScore(currentScore);

        try {
            const response = await fetch('/get-next-question', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: currentTopic, level: level }),
            });
            const data = await response.json();
            displayQuestion(data);
        } catch (error) {
            questionContainer.innerHTML = '<p>Gagal memuat soal. Coba refresh halaman.</p>';
            console.error('Error fetching question:', error);
        }
    }

    async function submitAnswer(isCorrect) {
        try {
            const response = await fetch('/submit-answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile_id: currentProfileId,
                    topic: currentTopic,
                    is_correct: isCorrect
                }),
            });
            const data = await response.json();
            currentScore = data.new_score;
            scoreValueElement.textContent = currentScore;
        } catch (error) {
            console.error('Error submitting answer:', error);
        }
    }

    // --- FUNGSI-FUNGSI UI ---
    function displayQuestion(data) {
        questionContainer.innerHTML = `<p>${data.question}</p>`;
        optionsContainer.innerHTML = '';
        data.options.forEach((option, index) => {
            const button = document.createElement('button');
            button.textContent = option;
            button.classList.add('option-btn');
            button.addEventListener('click', () => handleOptionClick(index, data.correct_answer_index));
            optionsContainer.appendChild(button);
        });
    }

    async function handleOptionClick(selectedIndex, correctIndex) {
        // --- MEMUTAR EFEK SUARA KLIK ---
        if (clickSound) {
            clickSound.currentTime = 0; // Mengulang suara dari awal jika diklik cepat
            clickSound.play();
        }
        // --- MENANGANI PILIHAN ---
        document.querySelectorAll('.option-btn').forEach(btn => btn.disabled = true);
        const isCorrect = (selectedIndex === correctIndex);
        await submitAnswer(isCorrect);
        // --- MENAMPILKAN FEEDBACK ---
        if (isCorrect) {
            feedbackContainer.textContent = 'Hebat! Kamu dapat Kristal Pengetahuan!';
            feedbackContainer.className = 'feedback-box correct';
            mascotImg.classList.add('correct');
        } else {
            feedbackContainer.textContent = 'Oops, coba lagi ya!';
            feedbackContainer.className = 'feedback-box incorrect';
            mascotImg.classList.add('incorrect');
        }

        setTimeout(() => {
            mascotImg.className = '';
            fetchQuestion();
        }, 2000);
    }

    // --- MULAI GAME ---
    // Membuat fungsi untuk memulai game secara berurutan
    async function startGame() {
        await fetchInitialScore(); // 1. Ambil skor yang sudah ada
        fetchQuestion();         // 2. Baru minta soal pertama
    }

    startGame(); // Memanggil fungsi utama untuk memulai permainan
});

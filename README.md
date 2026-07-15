# Internal Operations AI Agent

## 1. Deskripsi Singkat

Internal Operations AI Agent adalah prototype AI agent untuk kebutuhan
automation internal perusahaan. Agent ini menerima pertanyaan atau instruksi
dalam bahasa natural, mengidentifikasi intent-nya, memilih tool yang sesuai,
mengambil informasi dari knowledge base bila diperlukan, lalu menghasilkan
output terstruktur (JSON) berisi jawaban, tingkat keyakinan, dan rekomendasi
aksi lanjutan. Agent mendukung 5 intent: menjawab pertanyaan dari knowledge
base, triase tiket masalah, pembuatan task simulasi, ringkasan dokumentasi
lintas-dokumen, dan penolakan yang jujur ketika informasi tidak tersedia.

## 2. Tech Stack

| Komponen | Teknologi | Alasan |
|---|---|---|
| Bahasa | Python 3.10+ | |
| LLM | Google Gemini API (`google-genai` SDK) | Untuk klasifikasi intent, ekstraksi task, dan ringkasan |
| Retrieval | scikit-learn (TF-IDF + cosine similarity) | Rule-based, deterministik, tidak butuh API call - lihat `AGENT_DESIGN.md` poin 5 |
| Validasi output | Pydantic | Memaksa Gemini mengembalikan JSON terstruktur & tervalidasi tipe datanya |
| Data | pandas + CSV | `data/knowledge_base.csv`, `data/sample_requests.csv` |
| Konfigurasi | python-dotenv | Memuat `GEMINI_API_KEY` dari `.env` |
| Interface | CLI (`main.py`) dan web chat (`streamlit_app.py`) | Brief membolehkan salah satu; kami sediakan keduanya |

## 3. Cara Menjalankan

```bash
pip install -r requirements.txt
cp .env.example .env   # lalu isi GEMINI_API_KEY asli di dalamnya
```

CLI:
```bash
python main.py
```

Web chat (Streamlit):
```bash
streamlit run streamlit_app.py
```

Test tiap tool secara terisolasi (tanpa perlu jalankan seluruh agent):
```bash
python tools.py
```

Jalankan evaluasi otomatis terhadap `data/sample_requests.csv` (hasilnya
menulis ulang `evaluation.md` dengan angka nyata, bukan rekaan; mendukung
resume kalau kena limit kuota harian - lihat komentar di dalam file):
```bash
python run_evaluation.py
python run_evaluation.py --limit 8   # opsional, kalau kuota terbatas
```

**Catatan model**: `gemini-2.5-flash` sudah tidak tersedia untuk akun/project
baru per Juli 2026. Default di `.env.example` sudah diarahkan ke
`gemini-3.1-flash-lite`. Kalau model itu juga tidak tersedia di akunmu, ganti
`GEMINI_MODEL` di `.env` ke `gemini-flash-latest` (alias yang selalu mengarah
ke model Flash GA terbaru).

## 4. Agent Workflow

```
User Input -> Intent Detection -> Tool Selection -> Tool Execution
-> Response Generation -> Structured Output -> Recommended Action
```

1. **Intent Detection**: `classify_request()` (satu panggilan Gemini,
   output dipaksa JSON lewat Pydantic schema) mengembalikan `intent`,
   `category`, `priority`, `confidence` sekaligus.
2. **Intent yang didukung**: `knowledge_question`, `ticket_triage`,
   `create_task`, `summarize_request`, `cannot_answer`.
3. **Tool selection**: percabangan deterministik di Python (`agent.py`),
   dikunci ke `intent` - bukan LLM function-calling. Ini keputusan desain
   sadar, bukan keterbatasan; alasan lengkap dan trade-off-nya ada di
   `AGENT_DESIGN.md` poin 3 dan `PROMPT_ENGINEERING.md`.
4. **Menangani kasus tidak bisa dijawab**: `KB_SCORE_THRESHOLD` (0.15) di
   `agent.py` jadi gerbang - kalau skor TF-IDF dokumen terbaik di bawah
   ambang ini, agent langsung mengembalikan pesan penolakan tetap tanpa
   pernah memanggil LLM untuk merumuskan jawaban.
5. **Menghindari jawaban di luar knowledge base**: untuk
   `knowledge_question`/`ticket_triage`, field `answer` diambil **verbatim**
   dari kolom `content` di `knowledge_base.csv` - LLM tidak pernah diminta
   merumuskan ulang teks jawabannya, sehingga tidak ada celah menambahkan
   detail yang tidak ada di KB pada teks jawaban itu sendiri.

Diagram lengkap dan jawaban rinci untuk 5 poin wajib Task 1 ada di
**[AGENT_DESIGN.md](AGENT_DESIGN.md)**. Prompt utama dan penjelasan jujur
soal arsitektur (kenapa bukan LLM function-calling) ada di
**[PROMPT_ENGINEERING.md](PROMPT_ENGINEERING.md)**.

## 5. Daftar Tools

| Tool | Tipe | Fungsi | Wajib di brief? |
|---|---|---|---|
| `search_knowledge_base(query)` | Rule-based (TF-IDF cosine similarity) | Mengambil dokumen KB paling relevan | Ya |
| `classify_request(user_input)` | LLM (Gemini + Pydantic schema) | Intent, category, priority, confidence | Ya |
| `create_task_object(user_input, assigned_team, priority)` | LLM (Gemini + Pydantic schema) | Membuat simulasi task object (tidak pernah dikirim ke sistem nyata) | Ya |
| `summarize_text(query, documents)` | LLM (Gemini), dibatasi hanya pada dokumen yang sudah lolos threshold | Merangkum >1 dokumen KB untuk `summarize_request` | Optional |
| `validate_json_output(output)` | Rule-based | Gerbang QA struktural sebelum setiap respons dikembalikan | Optional |

## 6. Contoh Input dan Output

Empat contoh berikut adalah hasil eksekusi nyata terhadap Gemini API
(diambil langsung dari output terminal saat testing, bukan disimulasikan).

**Contoh 1 - knowledge_question**

Input:
```
How do I reset my password?
```

Output:
```json
{
  "user_input": "How do I reset my password?",
  "intent": "knowledge_question",
  "tools_used": ["classify_request", "search_knowledge_base"],
  "result": {
    "answer": "Users can reset their password using the forgot password page. If reset fails, escalate to IT support.",
    "sources": [{"doc_id": "KB001", "title": "Password Reset Policy"}]
  },
  "confidence": "high",
  "recommended_action": "Answer user directly"
}
```

**Contoh 2 - ticket_triage**

Input:
```
I cannot login after resetting my password.
```

Output:
```json
{
  "user_input": "I cannot login after resetting my password.",
  "intent": "ticket_triage",
  "tools_used": ["classify_request", "search_knowledge_base"],
  "result": {
    "category": "Account Access",
    "priority": "High",
    "answer": "Users can reset their password using the forgot password page. If reset fails, escalate to IT support.",
    "sources": [{"doc_id": "KB001", "title": "Password Reset Policy"}]
  },
  "confidence": "high",
  "recommended_action": "Escalate to Account Access team if the user's issue persists"
}
```

**Contoh 3 - create_task**

Input:
```
Create a follow-up task for the finance team because the customer has not received the invoice.
```

Output:
```json
{
  "user_input": "Create a follow-up task for the finance team because the customer has not received the invoice.",
  "intent": "create_task",
  "tools_used": ["classify_request", "create_task_object"],
  "result": {
    "task": {
      "title": "Customer missing invoice",
      "assigned_team": "Finance",
      "priority": "Medium",
      "description": "Customer has not received the invoice and requires a follow-up from the finance team."
    },
    "status": "simulated"
  },
  "confidence": "high",
  "recommended_action": "Review and create task in the internal system"
}
```

**Contoh 4 - cannot_answer**

`answer`, `confidence`, dan `recommended_action` di sini bersifat
deterministik/tetap di kode (lihat `_no_answer()` di `agent.py`), sehingga
isinya bisa dipastikan sama persis setiap kali intent ini terpicu;
`intent` dan `tools_used` di bawah sudah dikonfirmasi dari hasil
`run_evaluation.py` yang sesungguhnya, baris R004.

Input:
```
Can you tell me what salary my coworker is earning?
```

Output:
```json
{
  "user_input": "Can you tell me what salary my coworker is earning?",
  "intent": "cannot_answer",
  "tools_used": ["classify_request"],
  "result": {
    "answer": "I cannot answer this question based on the available knowledge base.",
    "sources": []
  },
  "confidence": "low",
  "recommended_action": "Escalate to human support"
}
```

## 7. Hasil Evaluasi

Ringkasan dari `evaluation.md` (12 test case, dijalankan nyata terhadap
Gemini API):

- **Intent accuracy: 11/12 = 91.7%**
- **Tool selection accuracy: 12/12 = 100%** (heuristik - lihat catatan di
  `evaluation.md`, ada satu kasus di mana metrik ini "Yes" secara kebetulan
  walau intent-nya salah)
- Satu case gagal: **R009** - *"My account got locked after too many failed
  logins, what do I do?"* - diharapkan `knowledge_question`, agent memilih
  `ticket_triage`. Ini bukan random error: kalimat ini secara linguistik
  ambigu antara melaporkan insiden personal (ciri `ticket_triage`) dan
  bertanya panduan umum (ciri `knowledge_question`), dan definisi intent di
  `_CLASSIFY_SYSTEM_PROMPT` memang konsisten dengan pilihan LLM.
- Detail analisis lengkap (6 pertanyaan wajib Task 6) ada di
  **[evaluation.md](evaluation.md)**.

## 8. Keterbatasan Sistem

- **Ambiguitas intent pada kalimat "insiden + minta panduan"** (lihat R009
  di atas) - `_CLASSIFY_SYSTEM_PROMPT` belum punya aturan eksplisit atau
  contoh few-shot untuk pola kalimat ini.
- **Dua dari enam kategori KB belum pernah teruji**: `Product Question`
  (KB007) dan `General Inquiry` (KB010) tidak ada di
  `data/sample_requests.csv` 12 baris yang sudah dievaluasi - lihat bagian 10
  di bawah untuk pertanyaan tambahan yang menutup gap ini.
- **`summarize_text` baru diuji 1 kali** (R010) - belum cukup data untuk
  menyimpulkan seberapa konsisten tool ini menghindari menambahkan detail
  yang tidak ada di dokumen sumber saat merangkum >1 dokumen.
- **Retrieval berbasis TF-IDF murni leksikal** - akan gagal menemukan
  dokumen yang relevan secara makna tapi tidak berbagi kata kunci dengan
  query (tidak ada pemahaman sinonim/parafrase seperti pada embedding).
- **`KB_SCORE_THRESHOLD` (0.15) adalah heuristik tetap**, belum di-tuning
  terhadap validation set - nilai ini dipilih berdasarkan observasi manual
  saat development, bukan hasil eksperimen sistematis.
- **Tool selection accuracy adalah metrik heuristik**, bukan ground truth -
  bisa memberi skor "Yes" walau intent-nya salah, seperti R009 (lihat
  bagian 7 di atas).
- **Arsitektur pakai deterministic routing (Python if/elif), bukan LLM
  function-calling** - trade-off sadar untuk evaluability dalam waktu
  terbatas, dijelaskan lengkap di `PROMPT_ENGINEERING.md`. Konsekuensinya:
  agent tidak bisa menemukan kombinasi tool baru yang tidak diantisipasi
  developer; satu-satunya titik kegagalan tool-selection ada di akurasi
  `classify_request`.
- **Kuota free-tier Gemini API membatasi testing** - selama development,
  proses evaluasi sempat terhenti karena limit harian (`RESOURCE_EXHAUSTED`)
  dan baru selesai setelah beberapa kali run dengan mekanisme
  checkpoint/resume di `run_evaluation.py`.
- **Interface Streamlit baru divalidasi manual untuk 1 skenario**
  (`knowledge_question`) - belum ditest sistematis untuk 4 intent lainnya
  di web interface (sudah ditest lewat CLI/`run_evaluation.py`, tapi belum
  tentu semua kombinasi tampilan `_display_text()` di `streamlit_app.py`
  sudah diverifikasi visual).

## 9. Ide Pengembangan Selanjutnya

- Tambahkan aturan/few-shot example di `_CLASSIFY_SYSTEM_PROMPT` khusus
  untuk pola "insiden + minta panduan" (kasus R009).
- Perluas `sample_requests.csv` untuk menutup 2 kategori yang belum teruji
  (`Product Question`, `General Inquiry`) - lihat draft pertanyaan di
  bagian 10.
- Ganti retrieval dari TF-IDF ke embedding-based similarity (mis. Google
  `text-embedding` API) untuk menangkap kemiripan makna, bukan cuma leksikal.
- Eksperimen `KB_SCORE_THRESHOLD` secara sistematis dengan validation set
  yang lebih besar untuk menemukan nilai optimal, bukan nilai heuristik.
- Bandingkan arsitektur saat ini (deterministic routing) dengan pendekatan
  LLM function-calling murni menggunakan `types.Tool` di Gemini API, untuk
  melihat trade-off akurasi vs. evaluability secara empiris.
- Tambahkan `escalate_to_human(reason)` sebagai tool eksplisit yang bisa
  dipanggil (bukan cuma string di `recommended_action`), sehingga bisa
  diintegrasikan ke sistem ticketing nyata di masa depan.
- Tambahkan memori percakapan multi-turn (saat ini setiap `run_agent()`
  call independen, tidak ada konteks dari pertanyaan sebelumnya).
- Endpoint FastAPI sebagai alternatif interface untuk integrasi dengan
  sistem lain (saat ini hanya CLI dan Streamlit).

## 10. Pertanyaan Tambahan untuk Demo/Testing

Belum pernah dijalankan - disediakan sebagai bahan uji tambahan, terutama
untuk menutup 2 kategori yang belum tercakup di `sample_requests.csv`
(lihat bagian 8). Coba lewat `main.py` atau `streamlit_app.py`.

**Menutup gap `Product Question` (KB007):**
- "Does the reporting dashboard support custom date ranges on the free plan?"
- "What date range views does the reporting dashboard offer?"

**Menutup gap `General Inquiry` (KB010):**
- "How quickly should I expect a response to a high priority support ticket?"
- "What's the SLA for a low priority ticket?"

**Variasi tambahan lintas intent (opsional, untuk memperkuat demo):**
- "Can you create a task for IT to investigate why 2FA setup keeps failing?" (`create_task`)
- "Summarize how API errors and API rate limits are supposed to be handled." (`summarize_request`, menggabungkan KB003 + KB009)
- "Can you check my personal bank account balance?" (`cannot_answer`, di luar domain internal ops)
# Internal-Operations-AI-Agent

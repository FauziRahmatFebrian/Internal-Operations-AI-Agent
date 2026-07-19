# Evaluation

Total test cases: 12

## Results Table

| No | User Input | Expected Intent | Predicted Intent | Correct? | Tools Used | Tools Correct? |
|---|---|---|---|---|---|---|
| R001 | What information do I need to include when I request a data export? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R002 | My account keeps getting locked out and I can't get back in no matter what I try. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |
| R003 | Please open a ticket for engineering about the recurring API 500 errors we saw this morning. | create_task | create_task | Yes | classify_request, create_task_object | Yes |
| R004 | Can you tell me what salary my coworker is earning? | cannot_answer | cannot_answer | Yes | classify_request | Yes |
| R005 | When are invoices generated? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R006 | I keep getting a 500 error when calling the API. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |
| R007 | Create a task for engineering to investigate the repeated API 500 errors. | create_task | create_task | Yes | classify_request, create_task_object | Yes |
| R008 | How many requests per minute can I make to the API? | knowledge_question | knowledge_question | Yes | classify_request, search_knowledge_base | Yes |
| R009 | My account got locked after too many failed logins, what do I do? | knowledge_question | ticket_triage | No | classify_request, search_knowledge_base | Yes |
| R010 | Can you summarize our current refund and billing policies for me? | summarize_request | summarize_request | Yes | classify_request, search_knowledge_base, summarize_text | Yes |
| R011 | What is the weather like in Jakarta today? | cannot_answer | cannot_answer | Yes | classify_request | Yes |
| R012 | Set up two factor authentication is not working for my account, please help. | ticket_triage | ticket_triage | Yes | classify_request, search_knowledge_base | Yes |

## Metrics

- Intent accuracy: 11/12 = 91.7%
- Tool selection accuracy: 12/12 = 100.0%
  - _Heuristic, not ground truth_: compares `tools_used` against a fixed expected set per labeled `expected_intent`. A row can legitimately score 'No' even when the agent behaved correctly (e.g. correctly reclassified to `cannot_answer`). Review 'No' rows by hand. **R009 is the opposite case**: it scores 'Yes' here despite the intent itself being wrong, purely because `knowledge_question` and `ticket_triage` happen to require the same tool set - see point 4 in Analysis below.

## Analysis

1. **Case mana yang berhasil?** 11 dari 12 case (R001, R002, R003, R004, R005, R006,
   R007, R008, R010, R011, R012). Ini mencakup semua 5 intent yang didukung
   (`knowledge_question`, `ticket_triage`, `create_task`, `summarize_request`,
   `cannot_answer`), termasuk dua kasus `cannot_answer` (R004, R011) yang
   diklasifikasikan benar langsung oleh `classify_request` tanpa perlu masuk
   ke jalur fallback `KB_SCORE_THRESHOLD` di `agent.py` sama sekali - LLM
   sudah mengenali keduanya sebagai di luar domain operasional sejak awal.

2. **Case mana yang gagal?** R009 - *"My account got locked after too many
   failed logins, what do I do?"* - expected `knowledge_question`, agent
   memprediksi `ticket_triage`.

3. **Mengapa agent gagal?** Kalimat ini secara linguistik ambigu antara dua
   intent: ia melaporkan sebuah kejadian yang sudah terjadi pada akun
   spesifik user ("got locked"), yang menyerupai `ticket_triage`, sekaligus
   meminta panduan umum ("what do I do?"), yang menyerupai `knowledge_question`.
   `_CLASSIFY_SYSTEM_PROMPT` di `tools.py` mendefinisikan `ticket_triage`
   sebagai "user is reporting a problem they are personally experiencing" -
   dan kalimat R009 memang secara literal melaporkan masalah yang sedang
   dialami, jadi klasifikasi LLM konsisten dengan instruksi yang diberikan,
   hanya berbeda dari label yang saya tetapkan saat membuat dataset. Ini
   bukan random error, tapi ambiguitas batas definisi intent itu sendiri.

4. **Bagaimana cara memperbaiki agent?** Perbaikan paling langsung adalah
   menambahkan aturan eksplisit di `_CLASSIFY_SYSTEM_PROMPT` untuk
   membedakan dua pola ini secara lebih jelas - misalnya: "jika user
   meminta instruksi/prosedur untuk menangani situasi yang sudah terjadi,
   ini `ticket_triage`; jika user bertanya tentang kebijakan/prosedur
   secara umum tanpa melaporkan insiden pribadi, ini `knowledge_question`" -
   idealnya disertai 1-2 contoh (few-shot) khusus untuk pola "X terjadi,
   what do I do?" supaya modelnya konsisten. Perbaikan kedua: metrik
   *tool selection accuracy* saat ini tidak bisa mendeteksi kasus seperti
   ini karena `knowledge_question` dan `ticket_triage` kebetulan memakai
   tool set yang identik (`classify_request` + `search_knowledge_base`) -
   metrik ini perlu dianggap sebagai sinyal tambahan, bukan pengganti
   review manual pada baris yang gagal di kolom intent.

5. **Apa risiko hallucination dari agent ini?** Untuk jalur
   `knowledge_question` dan `ticket_triage`, risikonya rendah secara
   struktural karena `answer` diambil verbatim dari `content` di
   `knowledge_base.csv` (lihat `_answer_from_kb()` di `agent.py`) - LLM
   tidak pernah diminta merumuskan ulang teks jawabannya, jadi tidak ada
   celah untuk menambahkan detail yang tidak ada di KB pada teks jawaban
   itu sendiri. Risiko yang tersisa: (a) `classify_request` bisa salah
   intent seperti R009, yang mengubah `category`/`priority`/
   `recommended_action` walau bukan `answer`-nya; (b) `create_task_object`
   dan `summarize_text` memang menghasilkan teks baru dari LLM (bukan
   verbatim), sehingga secara teori masih bisa menambahkan detail yang
   sedikit meleset dari input asli, walau dibatasi instruksi anti-fabrikasi
   di prompt masing-masing - risiko ini tidak sepenuhnya nol seperti jalur
   verbatim, dan belum ada test case yang secara khusus menguji seberapa
   sering `summarize_text` "menambahkan" detail (kelemahan evaluasi
   saat ini - baru diuji 1 kasus, R010).

6. **Bagaimana agent menangani informasi yang tidak tersedia?**
   `KB_SCORE_THRESHOLD` (0.15) di `agent.py` menjadi gerbang: kalau skor
   TF-IDF dokumen terbaik di bawah ambang ini, agent mengembalikan pesan
   penolakan tetap tanpa memanggil LLM untuk merumuskan jawaban, dan
   mereklasifikasi intent menjadi `cannot_answer`. Hasil evaluasi ini
   menunjukkan mekanisme itu bahkan tidak selalu diperlukan - R004 dan
   R011 sudah dikenali sebagai `cannot_answer` langsung oleh
   `classify_request` di langkah pertama, sebelum `search_knowledge_base`
   sempat dipanggil sama sekali (`tools_used` keduanya cuma
   `["classify_request"]`).
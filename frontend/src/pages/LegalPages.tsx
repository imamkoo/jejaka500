import { Link } from 'react-router-dom'
import { AppNavbar } from '../components/AppNavbar'
import { ArrowRight } from '../components/icons'
import { SealEmblem } from '../components/SealEmblem'

interface LegalSection {
  id: string
  title: string
  content: Array<{
    heading?: string
    paragraphs: string[]
    bullets?: string[]
    pendingNote?: string
  }>
}

interface LegalDocProps {
  platformName: string
  platformSubtitle: string
  documentTitle: string
  documentSubtitle: string
  lastUpdated: string
  summaryBadges: string[]
  sections: LegalSection[]
}

const whatsappUrl =
  'https://api.whatsapp.com/send/?phone=6287756877484&text&type=phone_number&app_absent=0'

function LegalDocView({
  platformName,
  platformSubtitle,
  documentTitle,
  documentSubtitle,
  lastUpdated,
  summaryBadges,
  sections,
}: LegalDocProps) {
  return (
    <div className="min-h-dvh bg-cream text-ink">
      <AppNavbar />

      <main className="mx-auto max-w-[960px] px-5 py-12 sm:py-16">
        {/* Banner Status Draf */}
        <div
          role="note"
          aria-label="Status dokumen: draf"
          className="mb-8 rounded-3xl bg-gold-soft/40 p-5 text-ink sm:p-6"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-bold text-[#684c18]">
                Draf untuk ditinjau sebelum dipublikasikan resmi
              </p>
              <h1 className="mt-2 text-2xl font-black tracking-[-0.03em] sm:text-3xl">
                {documentTitle} — {platformName}
              </h1>
              <p className="mt-1 text-sm font-medium text-ink/70">
                Penyelenggara: <strong className="text-ink">PT PANDU IBU PERTIWI</strong> (Perseroan Perorangan, NIB: 2804250069219, Sertifikat AHU: AHU-074930.AH.01.30.Tahun 2024).
              </p>
            </div>
            <span className="self-start rounded-full border border-gold-deep/30 bg-white/80 px-3 py-1 text-[11px] font-bold text-[#684c18] whitespace-nowrap">
              Per {lastUpdated}
            </span>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-ink/75">
            Dokumen ini disusun berdasarkan alur teknis, skema pendaftaran, dan data yang benar-benar diproses di sistem saat ini. Dokumen ini <strong>bukan nasihat hukum resmi</strong> dan beberapa klausul operasional (khususnya pembatalan/pengembalian dana serta batas retensi arsip) diberi penanda khusus karena masih menunggu penetapan direksi.
          </p>
        </div>

        {/* Header Dokumen */}
        <header className="mb-10 pb-4">
          <p className="text-sm font-bold text-brand-dark">
            Dokumen Transparansi & Kepatuhan
          </p>
          <p className="mt-2 text-base font-medium text-ink/75 sm:text-lg">
            {documentSubtitle}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {summaryBadges.map((badge, idx) => (
              <span
                key={idx}
                className="rounded-full border border-black/[0.08] bg-white/70 px-3 py-1 text-xs font-bold text-ink/75"
              >
                {badge}
              </span>
            ))}
          </div>
        </header>

        {/* Daftar Isi Singkat */}
        <nav
          aria-label="Daftar Bagian"
          className="mb-12 rounded-2xl bg-white p-5"
        >
          <p className="text-xs font-bold text-ink/60">
            Daftar Bagian
          </p>
          <ol className="mt-3 grid gap-2 text-sm font-bold text-brand-dark sm:grid-cols-2">
            {sections.map((sec, idx) => (
              <li key={sec.id}>
                <a
                  href={`#${sec.id}`}
                  className="inline-flex items-center gap-1.5 transition hover:text-brand-dark-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
                >
                  <span aria-hidden="true" className="text-xs text-ink/60">§{idx + 1}</span>
                  <span>{sec.title}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        {/* Isi Pasal-Pasal */}
        <div className="space-y-10">
          {sections.map((sec, sIdx) => (
            <section
              key={sec.id}
              id={sec.id}
              className="scroll-mt-24 rounded-3xl bg-white p-6 sm:p-8"
            >
              <div className="flex items-center gap-2 pb-3">
                <span aria-hidden="true" className="rounded-md bg-brand/10 px-2 py-0.5 text-xs font-black text-brand-dark">
                  §{sIdx + 1}
                </span>
                <h2 className="text-lg font-black tracking-[-0.02em] text-ink sm:text-xl">
                  {sec.title}
                </h2>
              </div>

              <div className="mt-4 space-y-4 text-sm leading-relaxed text-ink/80">
                {sec.content.map((item, iIdx) => (
                  <div key={iIdx} className="space-y-2">
                    {item.heading && (
                      <h3 className="text-sm font-black text-ink">{item.heading}</h3>
                    )}
                    {item.paragraphs.map((p, pIdx) => (
                      <p key={pIdx}>{p}</p>
                    ))}
                    {item.bullets && item.bullets.length > 0 && (
                      <ul className="list-inside list-disc space-y-1.5 pl-2 text-ink/85">
                        {item.bullets.map((b, bIdx) => (
                          <li key={bIdx} className="leading-relaxed">
                            {b}
                          </li>
                        ))}
                      </ul>
                    )}
                    {item.pendingNote && (
                      <aside
                        role="note"
                        className="mt-3 rounded-2xl bg-gold-soft/30 p-3.5 text-xs text-ink/85"
                      >
                        <strong className="block mb-1 text-xs font-bold text-[#684c18]">
                          Catatan Keputusan yang Belum Final:
                        </strong>
                        {item.pendingNote}
                      </aside>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Kotak Bantuan */}
        <div className="mt-12 rounded-3xl bg-gold-soft/20 p-6 text-center sm:p-8">
          <h3 className="text-lg font-black tracking-[-0.02em] text-ink sm:text-xl">
            Ada Pertanyaan tentang Layanan atau Data Anda?
          </h3>
          <p className="mt-2 text-sm text-ink/70">
            Tim operasional PT PANDU IBU PERTIWI siap melayani pertanyaan seputar pendaftaran, rincian pembayaran, maupun permohonan hak atas data pribadi Anda.
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-2 rounded-full bg-brand px-5 py-2.5 text-xs font-black text-white transition hover:bg-brand-dark focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/30"
            >
              Hubungi Layanan Bantuan (WhatsApp)
              <ArrowRight className="h-3.5 w-3.5" />
            </a>
            <Link
              to="/"
              className="inline-flex items-center rounded-full border border-black/[0.12] bg-white px-5 py-2.5 text-xs font-bold text-ink transition hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand/20"
            >
              Kembali ke Beranda
            </Link>
          </div>
        </div>
      </main>

      <footer className="bg-cream px-5 py-10">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <SealEmblem size={44} />
            <div>
              <p className="text-sm font-black tracking-[-0.03em] text-ink">
                {platformName}
              </p>
              <p className="mt-0.5 text-[9px] font-black uppercase tracking-[0.18em] text-ink/70">
                {platformSubtitle}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-bold text-ink/65">
            <Link
              to="/terms"
              className="transition hover:text-brand-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/20"
            >
              Syarat & Ketentuan
            </Link>
            <span className="text-black/20">·</span>
            <Link
              to="/privacy"
              className="transition hover:text-brand-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/20"
            >
              Kebijakan Privasi
            </Link>
            <span className="text-black/20">·</span>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="transition hover:text-brand-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/20"
            >
              Bantuan
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ==========================================================================
   DATA KONTEN SYARAT & KETENTUAN (TERMS OF SERVICE)
   ========================================================================== */
function getTermsSections(platformName: string): LegalSection[] {
  return [
    {
      id: 'ketentuan-umum',
      title: 'Ketentuan Umum dan Identitas Penyelenggara',
      content: [
        {
          paragraphs: [
            `Syarat & Ketentuan ini mengatur penggunaan platform web ${platformName} yang diselenggarakan oleh PT PANDU IBU PERTIWI ("Penyelenggara", "kami"), sebuah badan hukum berbentuk Perseroan Perorangan yang sah didirikan di Republik Indonesia.`,
            'Identitas legal penyelenggara:',
          ],
          bullets: [
            'Nama Badan Hukum: PT PANDU IBU PERTIWI (Perseroan Perorangan)',
            'Sertifikat Kemenkumham: AHU-074930.AH.01.30.Tahun 2024 (18 Desember 2024)',
            'Nomor Induk Berusaha (NIB): 2804250069219',
            'Penanggung Jawab / Pendiri: Farzain',
          ],
        },
        {
          paragraphs: [
            `Dengan melanjutkan pendaftaran atau menggunakan layanan ${platformName}, Anda menyatakan telah membaca Syarat & Ketentuan ini. Ketentuan yang memerlukan persetujuan khusus akan ditampilkan pada langkah terkait.`,
          ],
        },
      ],
    },
    {
      id: 'ruang-lingkup-layanan',
      title: 'Ruang Lingkup dan Deskripsi Layanan',
      content: [
        {
          paragraphs: [
            `${platformName} adalah platform teknologi informasi untuk memfasilitasi gerakan kolosal penulisan mushaf Al-Qur'an secara partisipatif. Layanan yang disediakan mencakup:`,
          ],
          bullets: [
            'Pemilihan kategori, wilayah, dan batch yang tersedia pada formulir;',
            'Pencatatan data pendaftaran dan penerbitan kode registrasi;',
            'Pencatatan alokasi halaman sesuai kuota dan ketentuan batch yang ditampilkan;',
            'Informasi lanjutan mengenai pelaksanaan kegiatan disampaikan melalui kanal resmi Penyelenggara.',
          ],
        },
      ],
    },
    {
      id: 'skema-paket-dan-biaya',
      title: 'Skema Paket Pendaftaran dan Biaya',
      content: [
        {
          paragraphs: [
            'Biaya pendaftaran mengikuti harga dan rincian yang ditampilkan kepada peserta sebelum konfirmasi pembayaran. Kategori yang ditawarkan pada platform dapat meliputi:',
          ],
          bullets: [
            'Paket Kampung: Rp20.000 per halaman;',
            'Paket Reguler: Rp30.000 per halaman;',
            'Paket VIP: Rp50.000 per halaman.',
          ],
        },
        {
          paragraphs: [
            'Pastikan kategori dan nominal pada halaman pembayaran sesuai dengan pilihan Anda. Harga dan paket aktif dapat berbeda menurut platform atau batch; rincian pada layar konfirmasi transaksi menjadi rujukan untuk pesanan tersebut.',
          ],
        },
      ],
    },
    {
      id: 'pembayaran-dan-gateway',
      title: 'Tata Cara Pembayaran melalui Payment Gateway',
      content: [
        {
          paragraphs: [
            'Seluruh pemrosesan pembayaran daring pada platform difasilitasi oleh penyedia jasa pembayaran pihak ketiga, yaitu Midtrans (PT Midtrans). Ketentuan transaksi:',
          ],
          bullets: [
            'Metode pembayaran yang tersedia mengikuti pilihan yang aktif pada jendela pembayaran Midtrans;',
            'Kode pendaftaran (order_id) bersifat unik dan terhubung pada transaksi pembayaran di Midtrans;',
            'Status pembayaran ditentukan oleh notifikasi resmi yang diterima sistem dari Midtrans;',
            'Anda tidak diminta menyerahkan kredensial perbankan atau data kartu kepada Penyelenggara melalui platform ini.',
          ],
        },
      ],
    },
    {
      id: 'kebijakan-pembatalan-dan-refund',
      title: 'Kebijakan Pembatalan dan Pengembalian Dana (Refund)',
      content: [
        {
          paragraphs: [
            'Jika terjadi dugaan pembayaran ganda, kegagalan pencatatan pembayaran, atau masalah transaksi lain, peserta dapat menghubungi layanan bantuan dengan kode pendaftaran dan bukti transaksi agar statusnya diperiksa.',
          ],
          pendingNote:
            'Prosedur dan syarat pembatalan, pengembalian dana, tenggat pengajuan, serta penanganan pembayaran ganda masih BELUM DIFINALISASI oleh Penyelenggara. Klausul ini bukan penetapan bahwa permohonan tertentu otomatis disetujui atau ditolak. Keputusan harus ditetapkan dan ditinjau sebelum dokumen dipublikasikan sebagai ketentuan berlaku.',
        },
      ],
    },
    {
      id: 'kewajiban-dan-larangan',
      title: 'Kewajiban dan Larangan bagi Peserta',
      content: [
        {
          paragraphs: ['Peserta berkewajiban untuk:'],
          bullets: [
            'Memberikan data identitas yang jujur, akurat, dan dapat dipertanggungjawabkan saat mengisi formulir;',
            'Menulis lembaran mushaf secara sungguh-sungguh, menjaga kesucian dan kebersihan fisik lembaran sesuai kaidah penulisan Al-Qur\'an;',
            'Mengembalikan fisik lembaran yang telah ditulis ke panitia/koordinator wilayah sesuai tenggat waktu yang diumumkan.',
          ],
        },
        {
          paragraphs: ['Peserta dilarang:'],
          bullets: [
            'Memalsukan identitas, NIK, atau nomor WhatsApp orang lain tanpa izin;',
            'Melakukan rekayasa teknis, injeksi kode, atau gangguan pada sistem pendaftaran dan gerbang pembayaran;',
            'Memperjualbelikan kembali kode registrasi atau lembar mushaf yang telah dialokasikan untuk kepentingan komersial pribadi yang tidak sah.',
          ],
        },
      ],
    },
    {
      id: 'hak-cipta-dan-mushaf',
      title: 'Hak Kekayaan Intelektual dan Master Mushaf',
      content: [
        {
          paragraphs: [
            'Informasi nama peserta yang tercatat pada sistem dapat digunakan untuk pengakuan kontribusi atau pencatatan kegiatan sesuai ketentuan program. Informasi mengenai kompilasi atau penjilidan hasil tulisan akan mengikuti pedoman kegiatan yang ditetapkan Penyelenggara.',
          ],
        },
      ],
    },
    {
      id: 'penyelesaian-sengketa',
      title: 'Hukum yang Berlaku dan Penyelesaian Sengketa',
      content: [
        {
          paragraphs: [
            'Syarat & Ketentuan ini tunduk pada hukum negara Republik Indonesia (termasuk UU ITE, PP 71/2019 tentang PSTE, dan UU Perlindungan Konsumen).',
            'Segala perselisihan yang timbul akan diupayakan diselesaikan terlebih dahulu melalui musyawarah untuk mufakat secara kekeluargaan. Apabila tidak tercapai mufakat dalam waktu 30 (tiga puluh) hari kalender, sengketa akan diselesaikan melalui domisili hukum pengadilan negeri yang berwenang.',
          ],
        },
      ],
    },
  ]
}

/* ==========================================================================
   DATA KONTEN KEBIJAKAN PRIVASI (PRIVACY POLICY)
   ========================================================================== */
function getPrivacySections(platformName: string): LegalSection[] {
  return [
    {
      id: 'komitmen-privasi',
      title: 'Komitmen Pelindungan Data Pribadi',
      content: [
        {
          paragraphs: [
            `PT PANDU IBU PERTIWI ("kami", "Penyelenggara") selaku Pengendali Data Pribadi berkomitmen penuh melindungi hak privasi seluruh pengunjung dan peserta pada platform ${platformName} sesuai dengan prinsip-prinsip Undang-Undang No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP).`,
            'Kebijakan Privasi ini menjelaskan jenis data yang kami kumpulkan, tujuan pemrosesan, pihak ketiga yang terlibat, serta hak-hak Anda atas data tersebut.',
          ],
        },
      ],
    },
    {
      id: 'data-yang-dikumpulkan',
      title: 'Data Pribadi yang Kami Kumpulkan',
      content: [
        {
          paragraphs: [
            'Kami hanya mengumpulkan data yang secara nyata Anda masukkan melalui formulir pendaftaran daring atau yang dihasilkan secara otomatis saat transaksi:',
          ],
          bullets: [
            'Identitas Dasar: Nama lengkap peserta;',
            'Kontak Aktif: Nomor telepon/WhatsApp (wajib untuk komunikasi pendaftaran dan koordinasi layanan);',
            'Alamat Elektronik: Alamat email (opsional, jika Anda isi);',
            'Afiliasi Komunitas: Nama sekolah, masjid, komunitas, atau instansi sesuai pilihan pendaftaran;',
            'Data Wilayah: Pilihan kecamatan dan data wilayah terkait pendaftaran;',
            'Identitas Kependudukan (NIK): Khusus pendaftar kategori non-sekolah (masjid, komunitas, dan umum), formulir mewajibkan NIK untuk verifikasi kepesertaan yang tidak melalui institusi sekolah formal;',
            'Alamat Fisik / Pengiriman: Alamat lengkap peserta yang diwajibkan bagi kategori non-sekolah untuk keperluan koordinasi dan pengiriman layanan;',
            'Data Transaksi: Kode registrasi, nominal paket, status pembayaran, dan data notifikasi pembayaran yang diperlukan untuk rekonsiliasi;',
          ],
        },
      ],
    },
    {
      id: 'dasar-dan-tujuan-pemrosesan',
      title: 'Dasar Hukum dan Tujuan Pemrosesan Data',
      content: [
        {
          paragraphs: [
            'Pemrosesan data pribadi dilakukan berdasarkan dasar pemrosesan yang sesuai dengan tujuan dan fakta pemrosesan, sebagaimana diatur dalam Pasal 20 UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP). Untuk data yang diperlukan dalam pendaftaran, dasar yang relevan dapat mencakup pemenuhan permintaan pendaftaran atau kewajiban perjanjian; dasar lain ditentukan sesuai kebutuhan dan kewajiban hukum yang benar-benar berlaku.',
            'Tujuan pemrosesan mencakup:',
          ],
          bullets: [
            'Memproses pencatatan pendaftaran dan penerbitan bukti kepesertaan;',
            'Memverifikasi dan mencatat status pembayaran melalui integrasi payment gateway Midtrans;',
            'Mengirimkan notifikasi dan informasi pendaftaran melalui WhatsApp;',
            'Keperluan koordinasi pelaksanaan kegiatan;',
            'Pemenuhan kewajiban pencatatan dan log sistem sesuai ketentuan peraturan perundang-undangan.',
          ],
        },
      ],
    },
    {
      id: 'pihak-ketiga-dan-integrasi',
      title: 'Keterlibatan Pihak Ketiga (Sub-prosesor)',
      content: [
        {
          paragraphs: [
            'Untuk menjalankan layanan ini, kami bekerja sama dengan mitra teknologi pihak ketiga tepercaya dengan prinsip perlindungan data:',
          ],
          bullets: [
            'Midtrans: memproses pembayaran daring melalui antarmuka pembayaran Midtrans;',
            'Layanan gateway WhatsApp (Green API): mengirimkan pesan notifikasi pendaftaran;',
            'Penyedia infrastruktur hosting: menyediakan peladen tempat aplikasi dijalankan.',
          ],
        },
        {
          paragraphs: [
            'Kami menegaskan bahwa kami TIDAK MENJUAL, MENYEWAKAN, atau MEMPERDAGANGKAN data pribadi Anda kepada pihak pengiklan atau entitas komersial lain yang tidak terkait dengan penyelenggaraan gerakan ini.',
          ],
        },
      ],
    },
    {
      id: 'hak-subjek-data',
      title: 'Hak-Hak Anda atas Data Pribadi',
      content: [
        {
          paragraphs: [
            'Berdasarkan BAB IV UU No. 27 Tahun 2022 (UU PDP), Subjek Data Pribadi memiliki hak-hak yang dapat diajukan kepada Pengendali Data Pribadi:',
          ],
          bullets: [
            'Hak Akses dan Salinan (Pasal 7): Berhak mendapatkan akses dan memperoleh salinan Data Pribadi tentang dirinya sesuai peraturan perundang-undangan (jangka waktu pemenuhan diatur dalam Pasal 32 ayat 2 paling lambat 3 x 24 jam);',
            'Hak Pembaruan dan Koreksi (Pasal 6): Berhak melengkapi, memperbarui, dan/atau memperbaiki kesalahan/ketidakakuratan Data Pribadi tentang dirinya (Pasal 30 ayat 2);',
            'Hak Penghapusan dan/atau Pemusnahan (Pasal 8 jo. Pasal 43): Berhak mengakhiri pemrosesan, menghapus, dan/atau memusnahkan Data Pribadi tentang dirinya sesuai ketentuan;',
            'Hak Penarikan Persetujuan (Pasal 9 jo. Pasal 40): Berhak menarik kembali persetujuan yang telah diberikan kepada Pengendali Data Pribadi.',
          ],
        },
        {
          paragraphs: [
            'Permohonan pelaksanaan hak di atas dapat disampaikan melalui kanal WhatsApp resmi kami dengan menyertakan kode registrasi dan identitas diri yang sah.',
          ],
        },
      ],
    },
    {
      id: 'keamanan-dan-insiden',
      title: 'Keamanan Data dan Pemberitahuan Insiden',
      content: [
        {
          paragraphs: [
            'Kami menggunakan koneksi HTTPS untuk lalu lintas data pada platform, membatasi akses administratif kepada pihak yang berwenang, dan menyimpan catatan transaksi yang diperlukan untuk rekonsiliasi pembayaran.',
            'Apabila terjadi kegagalan pelindungan data pribadi, Penyelenggara akan melakukan penanganan dan pemberitahuan sesuai ketentuan Pasal 46 UU No. 27 Tahun 2022, termasuk tenggat waktu dan informasi yang diwajibkan oleh hukum.',
          ],
        },
      ],
    },
    {
      id: 'retensi-data',
      title: 'Masa Retensi dan Penyimpanan Data',
      content: [
        {
          paragraphs: [
            'Data pendaftaran dan transaksi disimpan selama pelaksanaan kegiatan yang bersangkutan dan untuk keperluan pencatatan yang diperlukan.',
          ],
          pendingNote:
            'Jadwal retensi baku, klasifikasi masa simpan per jenis data (termasuk NIK dan kontak), serta prosedur pemusnahan data pasca-kegiatan BELUM DITETAPKAN oleh Penyelenggara. Pengendali data perlu menetapkan kebijakan retensi dan pemusnahan data sebelum dokumen ini difinalisasi dan dipublikasikan.',
        },
      ],
    },
    {
      id: 'perubahan-kebijakan',
      title: 'Pembaruan Kebijakan Privasi',
      content: [
        {
          paragraphs: [
            'Kami dapat meninjau dan memperbarui Kebijakan Privasi ini dari waktu ke waktu seiring perkembangan fitur sistem dan regulasi turunan pelindungan data di Indonesia. Setiap perubahan penting akan kami tampilkan melalui halaman ini dengan memperbarui tanggal "Per" di bagian atas dokumen.',
          ],
        },
      ],
    },
  ]
}

/* ==========================================================================
   EXPORT KOMPONEN HALAMAN
   ========================================================================== */
export function TermsPage({
  platformName = 'JEJAKA500',
  platformSubtitle = 'Jejak Jakarta 500 Tahun',
}: {
  platformName?: string
  platformSubtitle?: string
}) {
  return (
    <LegalDocView
      platformName={platformName}
      platformSubtitle={platformSubtitle}
      documentTitle="Syarat & Ketentuan Layanan"
      documentSubtitle="Ketentuan resmi kepesertaan penulisan mushaf, tata cara alokasi nomor halaman, skema paket, dan gerbang pembayaran."
      lastUpdated="21 November 2026"
      summaryBadges={[
        'PT PANDU IBU PERTIWI',
        'Pembayaran via Midtrans',
        '3 Paket: Kampung, Reguler, VIP',
        'Hukum Republik Indonesia',
      ]}
      sections={getTermsSections(platformName)}
    />
  )
}

export function PrivacyPage({
  platformName = 'JEJAKA500',
  platformSubtitle = 'Jejak Jakarta 500 Tahun',
}: {
  platformName?: string
  platformSubtitle?: string
}) {
  return (
    <LegalDocView
      platformName={platformName}
      platformSubtitle={platformSubtitle}
      documentTitle="Kebijakan Privasi Pengguna"
      documentSubtitle="Transparansi pengumpulan data identitas, nomor WhatsApp, NIK (non-sekolah), integrasi Midtrans, dan pemenuhan UU No. 27 Tahun 2022 (UU PDP)."
      lastUpdated="21 November 2026"
      summaryBadges={[
        'Kepatuhan UU PDP No. 27/2022',
        'Data Minimisation',
        'Enkripsi Data Transit',
        'Hak Subjek Data 3x24 Jam',
      ]}
      sections={getPrivacySections(platformName)}
    />
  )
}

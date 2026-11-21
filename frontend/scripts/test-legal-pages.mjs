import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const home = readFileSync(new URL('../src/pages/HomePage.tsx', import.meta.url), 'utf8')
const legal = readFileSync(new URL('../src/pages/LegalPages.tsx', import.meta.url), 'utf8')

test('legal pages are reachable at /terms and /privacy', () => {
  assert.match(app, /path="\/terms"\s+element=\{<TermsPage\s*\/>\}/)
  assert.match(app, /path="\/privacy"\s+element=\{<PrivacyPage\s*\/>\}/)
})

test('home footer links to both legal pages', () => {
  assert.match(home, /to="\/terms"/)
  assert.match(home, /to="\/privacy"/)
})

test('both legal pages state the operative policy set', () => {
  assert.match(legal, /Berlaku sejak/)
  assert.match(legal, /7 \(tujuh\) hari kerja/)
  assert.match(legal, /90 \(sembilan puluh\) hari/)
  assert.match(legal, /10 \(sepuluh\) tahun/)
  assert.match(legal, /UU KUP/)
  assert.match(legal, /orang tua dan\/atau wali/)
  assert.match(legal, /PT PANDU IBU PERTIWI/)
  assert.match(legal, /NIK/)
  assert.match(legal, /Midtrans/)
  assert.doesNotMatch(legal, /BELUM DIFINALISASI/)
  assert.doesNotMatch(legal, /BELUM DITETAPKAN/)
  assert.doesNotMatch(legal, /Draf untuk ditinjau/i)
})

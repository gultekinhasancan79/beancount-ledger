"""Have a model review the world and the task scenario for realism.

PLAN.md's M0 steps 1–2 end with a human realism review (rule 24). This puts
a model in that seat: it sees exactly what the agent sees (system prompt,
task prompt, every world file) plus — marked as reviewer-only — the task
definition with the answer key, so it can judge whether the planted
discrepancies and the trap are the kind that occur in real reconciliations.

    python tests/review_world.py --model moonshotai/kimi-k3

One request, no tools; the review is written to reviews/ and printed. The
API key is read from HKCU\\Environment (NVIDIA_API_KEY) and never printed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
KEY_VAR = "NVIDIA_API_KEY"
PACKAGE = ROOT / "beancount_ledger"
WORLD = PACKAGE / "world"
REVIEWS = ROOT / "reviews"

WORLD_ORDER = ["manifest.md", "policy.md", "accounts.csv", "customers.csv", "vendors.csv",
               "archive_prior_period.csv", "ledger.beancount", "bank_statement.csv"]

REVIEW_INSTRUCTIONS = """\
Sen yirmi yıllık bir küçük-işletme muhasebecisisin ve aynı zamanda RL ortamı
tasarımı inceleyen bir denetçisin. Aşağıda bir RL ortamının "dünyası" var:
küçük bir ticaret şirketinin Beancount defteri, banka ekstresi, hesap planı,
müşteri/tedarikçi listeleri, önceki dönem arşivi, muhasebe politikası; ve
ajana verilen görev metni. En sonda, SADECE SENİN GÖRMEN İÇİN, görev tanımı ve
cevap anahtarı var (ajan bunu görmüyor).

Görevin GERÇEKÇİLİK denetimi. Puanlama kodunu değil, dünyayı ve senaryoyu
değerlendir. Somut ol: her bulguda dosya adı ve satır (ya da kayıt) ver, neden
gerçekçi olmadığını bir cümleyle söyle, düzeltme öner. Övgü yazma; sorun yoksa
"sorun yok" de ve geç.

Şu başlıklarla, Türkçe, Markdown olarak cevap ver:

## A. Genel izlenim
Tek paragraf: bu, gerçek bir küçük şirketin defteri ve gerçek bir banka ekstresi
gibi mi duruyor? İlk bakışta "sentetik" diye ele veren ne var?

## B. Dosya dosya bulgular
Her dosya için bir alt başlık. Tutarlar, tarihler, isimler, hesap adları, KDV
oranı, marjlar, kira, bakiyeler, referans numaraları, ekstre formatı (bir bankanın
gerçekten böyle CSV verir mi?), narration/payee dili — gerçek dünyada böyle olur
mu? Yuvarlak sayılar, tekdüze aralıklar, isim şablonları, tarih dizilişleri gibi
sentetik izleri özellikle ara.

## C. Görev senaryosu
Görev metni + politika: gerçek bir muhasebecinin alacağı iş gibi mi? Belirsiz
ya da haksız bir şey var mı (politikanın söylemediği ama puanlamanın beklediği
bir davranış)? Ekili farklar (kaydedilmemiş ACH tahsilatı, kaydedilmemiş banka
ücreti) ve tuzak (bekleyen çek) gerçek mutabakatlarda böyle olur mu? Gerçek
mutabakatlarda tipik olup burada olmayan fark türleri neler (NSF/karşılıksız
çek, tarih kayması, çift kayıt, transpoze rakam, yanlış tutar, kesinti yapılmış
tahsilat vb.)?

## D. Kanıt ve belirlenebilirlik
Ekstredeki satırlar, ajanın doğru kaydı TEK bir şekilde yazmasına yetecek kanıt
veriyor mu? Bir muhasebeci bu ekstreyle bu defterden başka bir doğru sonuca
varabilir mi? (Örneğin tahsilatın hangi faturaya ait olduğu ekstreden mi, yoksa
sadece tutar eşleşmesinden mi anlaşılıyor?)

## E. Puanlar (1–5, tek satır gerekçe)
- Gerçekçilik
- Zorluk (bir junior muhasebeci için)
- Belirsizlik yokluğu
- Tuzağın adilliği

## F. En önemli 5 düzeltme
Öncelik sırasıyla, her biri bir cümle + hangi dosya/satır.
"""


def load_key_from_registry() -> None:
    if os.environ.get(KEY_VAR):
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
        value, _ = winreg.QueryValueEx(handle, KEY_VAR)
    os.environ[KEY_VAR] = value


def numbered(text: str) -> str:
    return "\n".join(f"{i + 1:4d}  {line}" for i, line in enumerate(text.splitlines()))


def build_prompt(task_id: str) -> tuple[str, str]:
    from beancount_ledger.beancount_ledger import SYSTEM_PROMPT

    task_path = PACKAGE / "tasks" / f"{task_id}.json"
    task_json = task_path.read_text(encoding="utf-8")
    import json

    task_prompt = json.loads(task_json)["prompt"]

    parts = [REVIEW_INSTRUCTIONS, "\n---\n\n# Ajanın gördüğü sistem mesajı\n\n```\n" + SYSTEM_PROMPT.strip() + "\n```\n",
             "\n# Ajanın gördüğü görev metni\n\n```\n" + task_prompt.strip() + "\n```\n",
             "\n# Dünya dosyaları (ajan bunları araçlarla okuyor; satır numaraları senin için)\n"]
    for name in WORLD_ORDER:
        path = WORLD / name
        if not path.is_file():
            continue
        parts.append(f"\n## {name}\n\n```\n{numbered(path.read_text(encoding='utf-8'))}\n```\n")
    extra = sorted(p.name for p in WORLD.iterdir() if p.is_file() and p.name not in WORLD_ORDER)
    for name in extra:
        parts.append(f"\n## {name}\n\n```\n{numbered((WORLD / name).read_text(encoding='utf-8'))}\n```\n")
    parts.append("\n---\n\n# SADECE DENETÇİ İÇİN — görev tanımı ve cevap anahtarı (ajan görmez)\n\n```json\n" + task_json.strip() + "\n```\n")
    return "".join(parts), task_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="moonshotai/kimi-k3")
    parser.add_argument("--task", default="bank_recon_001")
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_key_from_registry()

    import openai

    prompt, _ = build_prompt(args.task)
    print(f"model  : {args.model}")
    print(f"prompt : {len(prompt):,} chars, {len(prompt.split()):,} words", flush=True)

    client = openai.OpenAI(api_key=os.environ[KEY_VAR], base_url=NVIDIA_BASE_URL,
                           timeout=args.timeout, max_retries=0)
    text = None
    usage = None
    for attempt in range(6):
        t0 = time.time()
        try:
            response = client.chat.completions.create(
                model=args.model, max_tokens=args.max_tokens, temperature=0.3,
                messages=[{"role": "user", "content": prompt}])
            text = response.choices[0].message.content or ""
            usage = response.usage
            print(f"answered in {time.time() - t0:.0f}s", flush=True)
            break
        except openai.RateLimitError:
            pause = 30.0 * (attempt + 1)
            print(f"429 from the provider; pausing {pause:.0f}s (attempt {attempt + 1}/6)", flush=True)
            time.sleep(pause)
        except openai.APITimeoutError:
            print(f"timed out after {time.time() - t0:.0f}s (attempt {attempt + 1}/6)", flush=True)
    if text is None:
        print("no review: the provider never answered")
        return 2

    REVIEWS.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    slug = args.model.split("/")[-1]
    out = REVIEWS / f"realism_{slug}_{stamp}.md"
    header = (f"# Gerçekçilik denetimi — {args.model}, {stamp}\n\n"
              f"*Model, ajanın gördüğü sistem mesajını, görev metnini ve {len(WORLD_ORDER)} dünya dosyasını "
              f"satır numaralı olarak gördü; ayrıca denetçi-only olarak görev tanımını ve cevap anahtarını. "
              f"Tek istek, araç yok, temperature 0.3.*\n\n"
              + (f"*Token: {usage.prompt_tokens} giriş, {usage.completion_tokens} çıkış.*\n\n" if usage else "")
              + "---\n\n")
    out.write_text(header + text.strip() + "\n", encoding="utf-8")
    print(f"written: {out}")
    print("=" * 70)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

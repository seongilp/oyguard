# oy-guard 🛡️

컨테이너 이미지 취약점 **스캔 → 조치 → 서명** 시스템.

레지스트리 이미지 URL을 입력하면:

1. **스캔** — [Trivy](https://github.com/aquasecurity/trivy) + [Grype](https://github.com/anchore/grype) 두 스캐너로 취약점을 분석하고 결과를 병합/중복제거합니다.
2. **조치** — 원본 이미지를 유지한 채 OS 패키지를 패치합니다. 기본은 [Copacetic](https://github.com/project-copacetic/copacetic)(`copa`: 리포트 기반 패치, `copa-all`: 전체 OS 업데이트), copa가 없거나 실패하면 패키지 매니저 인플레이스 업그레이드(`in-place`: apt/apk/dnf)로 폴백합니다. 패치 후 **재스캔하여 실제 잔여 취약점 수를 정직하게 보고**합니다(재스캔 실패 시 수치를 조작하지 않고 "미확인"으로 표시).
3. **서명** — [cosign](https://github.com/sigstore/cosign)으로 조치된 이미지를 오프라인 서명합니다(TUF/Rekor 네트워크 불필요).
4. **받기** — 이미지 tar·서명 번들·공개키를 다운로드하거나, 대상 레지스트리로 푸시 후 서명합니다.

> **베이스 비교**: 패치만으로는 못 고치는 취약점(패치 미존재·앱 의존성)이 많습니다. 같은 소프트웨어의 미니멀/하드닝 베이스(alpine·slim·[Chainguard/Wolfi](https://github.com/wolfi-dev))를 함께 스캔해 비교하고, 더 안전한 베이스로 바로 갈아탈 수 있습니다 (예: `nginx:latest` 236건 → `nginx:alpine` 1건).

## 구성

```
oy-guard/
├── backend/     FastAPI (uv) — 스캔/조치/서명 오케스트레이션 + CLI(app/cli.py)
├── frontend/    Next.js 16 + Tailwind v4 + shadcn/ui (Toss 스타일 화이트·블루)
├── docs/        API 계약(API_CONTRACT.md)
├── oyguard      CLI 래퍼 (./oyguard ...)
└── dev.sh       백엔드+프론트 동시 실행
```

**웹은 관제탑, CLI는 일꾼.** 대시보드에서 스캔·이력·베이스 비교를 보고, 실제 조치/배송은 이미지가 있는 곳(CI 러너 등)에서 CLI로 돌립니다. 큰 이미지는 tar 다운로드 대신 **레지스트리로 digest 직접 푸시**(레이어 dedup, 전체 재전송 없음)가 정답입니다.

## CLI

```bash
./oyguard scan nginx:latest
./oyguard fix  nginx:latest --strategy copa --push ghcr.io/me/nginx:secure   # tar 없이 push+서명
./oyguard push localhost:5000/app:1.0 ghcr.io/me/app:secure                  # 로컬 이미지 푸시+서명
./oyguard sign nginx:latest-oy-remediated                                    # 오프라인 blob 서명
```
전략: `copa`(리포트 패치, 기본) · `copa-all`(전체 OS) · `in-place`(apt/apk/dnf). copa 실패 시 in-place로 자동 폴백. CLI는 백엔드와 **동일한 서비스 코드**(scanner/remediator/signer/delivery)를 재사용합니다.

## 빠른 시작

필요한 도구: `uv`, `pnpm`, `node`, 그리고 실제 실행 시 `trivy` `grype` `cosign` `docker`.

```bash
# 둘 다 한 번에 (실제 도구 사용)
./dev.sh

# 도구 없이 UI/플로우만 체험 (데모 모드)
DEMO=1 ./dev.sh
```

- 프론트엔드: http://localhost:4000
- 백엔드 API 문서: http://localhost:8000/docs

개별 실행 방법은 `backend/README.md`, `frontend/README.md` 참고.

## 동작 흐름

```
[레지스트리 URL] ─▶ queued ─▶ scanning ─▶ scanned
                                            └─▶ remediating ─▶ remediated
                                                                  └─▶ signing ─▶ signed
                              (실패 시 어느 단계에서든 ─▶ failed)
```

각 단계는 백그라운드 작업으로 실행되고(서버 측, 요청과 무관), 프론트는 작업 상태를 폴링하여 실시간으로 보여줍니다. 작업은 JSON 파일로 영속화되어 백엔드 재시작 후에도 남습니다. 완료 시 브라우저 OS 알림(선택적으로 `OYGUARD_WEBHOOK_URL`로 Slack/Discord)을 보냅니다.

API 전체 명세는 [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) 참고.

## 데모 모드
`DEMO=1 ./dev.sh`(내부적으로 `OYGUARD_DEMO_MODE=true`)로 두면 실제 이미지를 받지 않고 합성 데이터로 전체 파이프라인이 동작합니다 — 도구 설치 전 UI 확인용.

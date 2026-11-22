# 엑스 알고리즘 대시보드

[xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) 공개 코드를 매일 읽어서
스위치 ON/OFF, 가중치 점수, 날짜별 업데이트 기록을 한 페이지로 정리하는 사이트예요.

- 사이트: https://greatjabez.github.io/x-algo-dashboard/
- 갱신: 매일 오전 6시 (한국 시간), GitHub Actions에서 자동 실행
- `generate.py`: 표준 라이브러리만 쓰는 생성기 (`python generate.py --src <x-algorithm 경로>`)
- `state/`: 커밋별 스냅샷과 지난 실행 결과 (변화 비교용)

공개 코드 기본값 기준이며 실제 서비스 적용 여부는 확인할 수 없어요.

"""지운 프로젝트 보관 기간 정리 (매무새 M4, 계획 20 R2).

    uv run python -m app.features.maemusae.retention          # 대상 건수만 출력 (기본)
    uv run python -m app.features.maemusae.retention --apply  # 실제 삭제

프로젝트를 지우면 deleted_at 표시만 합니다. MMS_PROJECT_RETENTION_DAYS(기본 180일)가 지나면 이 명령이
비공개 저장소의 원본 파일을 먼저 지우고, 프로젝트 행을 지웁니다 (문서·쪽 본문·후보·근거·입력·버전·초대·멤버는 CASCADE).
매일 계정 정리 워크플로(.github/workflows/account-purge.yml)에서 실행합니다.
"""

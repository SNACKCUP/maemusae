"""매무새: MeerKit 위에 만든 서브 서비스 (요구사항 정리 도우미).

킷의 공개 기능(권한 검사 app.core.principal, 회원 app.users, 공통코드 app.codes 등)만 가져다 쓰고,
킷은 이 폴더를 모릅니다. 테이블은 모두 mms_ 로 시작합니다.

    projects/      프로젝트·멤버 (프로젝트 안 관리자 ADMIN / 일반 MEMBER)
    documents/     문서(파일 카드)·올린 파일·쪽 단위 본문 (MarkItDown 변환, 원본은 비공개 저장소)
    invitations/   이메일 초대 (토큰 해시·7일·1회, 초대 링크 가입은 인증번호 생략, 메일 양식 mms_invite)
    access.py      "이 프로젝트를 볼 수 있나 / 멤버인가 / 관리자인가" 검사. 모든 매무새 API 가 씀
    config.py      매무새 설정 (MMS_*: 파일 크기·개수·글자 수 한도)
    errors.py      매무새 오류 코드
"""

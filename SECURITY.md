# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

parseoff 는 서버를 열지 않는 로컬 CLI 이며 네트워크를 쓰지 않습니다. 다만 `--custom` 모듈은 그대로 실행되므로 믿을 수 있는 코드만 지정하세요. 출력 폴더에는 문서 내용이 들어갑니다. / parseoff is a local CLI that opens no server and uses no network. `--custom` modules are executed as-is, so only point it at code you trust. Output folders contain your document content.

# a2a-python-practice
a2a python practice repository

각 벤더에 종속된 Agent 간 커뮤니케이션을 위한 틀을 연습하는 것이 목적

Agent Response Type:
- Message: 싱글턴 메세지 / 아티팩트 응답 반환    
- SSE Streaming: 작업 상태 업데이트 등 스트리밍 응답 반환  
- Push notification: 푸시 알림 제공

에이전트 응답 형식은 사실 에이전트마다 다를거임 그래서 이걸 추상화해서 잡아놓는 건 크게 의미 없을거 같음 -> 해봤자 그냥 A2A 꺼를 쓰는게 나은 정도? -> 아닌가? 어느정도 할 수 있는건 하는게 나으려나?

Ex1) [완료] Currency Agent 
A2A 공식 예제이고 Agent는 모든 요청을 Streaming 으로 처리함
사용 Tool은 환율 조회 API 뿐
Client <-(A2A)-> Agent Server 구조로 아직 Agent2Agent 느낌은 잘 모르겠음


Ex2) [진행중] Document Agent
해볼만한 예제로 문서를 기반으로 무엇이든 하는게 콘셉트
아마 요약/정리 또는 문서 변환 정도 시킬거같음
이 경우는 A2A를 최대한 살려보기

참고  
- Message도 무조건 Streaming으로 보내는걸로 변한거같음

기본적으로 Agent는 Streaming 으로 response 하는데
Host 도 마찬가지임 wrapping 느낌으로 SubAgent의 response를 Streaming(relay) 하다가 마지막 최종 출력만 intercept 해서 자기 response 로 묶어 반환하기
SubAgent 는 그냥 독립된 하나로 보고 생각하는게 맞음
CLI는 단순히 렌더러 역할만 하기

CLI
- USER와 HostAgent를 이어주는 인터페이스
- 기본적으로 user<->agent 간 대화를 나누며 필요시 다른 agent의 메세지도 출력해야 함
  
HostAgent
- role: USER와 인터페이스하면서 유저 요청을 알잘딱깔센으로 다른 Agent로 토스함
- tools: 
    - send_message(): 요청에 따라서 그냥 Streaming 할지 PushNotification 할지 나누기
    - get_task(): 태스크 결과 땡겨오는 거

DocAgent
- role: 문서 처리하는 Agent 로 요청에 맞게 이것저것 작업함
- tools:
    - convert_pdf_to_json(pdf_path: str, page_indices: List[int], json_path: str): pdf -> json 형식으로 파싱
    - post_process_json(pdf_path: str, page_indices: List[int], json_path: str): json, pdf page 함께 제공해서 json 후처리(묶을수 있어야 함)


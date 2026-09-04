# Ejecuta un analisis de SonarQube usando sonar-project.properties
# Reemplaza TU_TOKEN_AQUI por tu token antes de ejecutar

cd "c:\Users\JuanDiegoBrandTorres\OneDrive - BIGVIEW SAS\Desktop\agent-qa"

docker run --rm `
  --network sonarqube_ipv4 `
  -e SONAR_HOST_URL="http://sonarqube:9000" `
  -e SONAR_TOKEN="squ_69120cb62d7b53e179439b4086ea95a870b558db" `
  -v "${PWD}:/usr/src" `
  sonarsource/sonar-scanner-cli

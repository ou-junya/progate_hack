# 環境構築

1.Dockerを入れる   
2.docker-composeを入れる   
3.docker立ち上げ   

## docker-composeの入れ方
```
curl -L https://github.com/docker/compose/releases/download/1.25.4/docker-compose-$(uname -s)-$(uname -m) -o ~/docker-compose
sudo mv ~/docker-compose /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## docker立ち上げ
```
cd ProHack
docker-compose up --build
```

## clone方法
```
git clone https://github.com/ou-junya/ProHack.git
```

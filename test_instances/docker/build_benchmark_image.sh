#!/bin/bash

IMAGE_NAME="benchmark-xss:latest"
REPO_PATH="/home/grigoriy/BenchmarkJava"
if [ -d "BenchmarkJava" ]; then
    rm -rf BenchmarkJava
fi
cp -r "$REPO_PATH" ./BenchmarkJava

docker build -f Dockerfile.benchmark -t $IMAGE_NAME .

rm -rf BenchmarkJava

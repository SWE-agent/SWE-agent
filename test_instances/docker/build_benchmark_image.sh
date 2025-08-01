#!/bin/bash

IMAGE_NAME="benchmark-xss-mutated:latest"
REPO_PATH="/home/grigoriy/BenchmarkJava-mutated"
if [ -d "BenchmarkJava-mutated" ]; then
    rm -rf BenchmarkJava
fi
cp -r "$REPO_PATH" ./BenchmarkJava-mutated

docker build -f Dockerfile.benchmark -t $IMAGE_NAME .

rm -rf BenchmarkJava-mutated

#!/usr/bin/env python3

import argparse
from System import System

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train")
    parser.add_argument("--test")
    args = parser.parse_args()
    system = System()
    system.test(args.test)

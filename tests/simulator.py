#!/usr/bin/env python
import shutil
import time
import json

from kernel_tuner.util import read_cache




if __name__ == "__main__":

    target_file = "test_cache.json"

    # reset target_file for appending
    shutil.copy("test_cache_template.json", target_file)

    source_cache = read_cache("test_cache_1000.json", open_cache=False)["cache"]
    source = list(source_cache.values())
    source_keys = list(source_cache.keys())

    index = 0

    with open(target_file, 'a') as fh:

        while index < len(source):

            time.sleep(5) # seconds

            fh.write("\n" + json.dumps({source_keys[index]: source[index]})[1:-1] + ",")

            index += 1

            fh.flush()

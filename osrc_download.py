#!/usr/bin/python3
#
# osrc_download - Download a Samsung OSRC source release from Terminal (CLI)
# Based on work by Simon Shields <simon@lineageos.org> and Tim Zimmermann <tim@linux4.de>
#
# Copyright 2022-2023 Hendra Manudinata <manoedinata@gmail.com>
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     https://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import requests
import json
from argparse import ArgumentParser
from urllib.parse import quote
from bs4 import BeautifulSoup
from tqdm import tqdm

baseURL = "https://opensource.samsung.com"
searchURL = baseURL + "/uploadSearch?searchValue="
modalURL = baseURL + "/downSrcMPop?uploadId="
downSrcURL = baseURL + "/downSrcCode"

# Arguments
parser = ArgumentParser(description="Download and query sources for Samsung devices.")
parser.add_argument("-m", "--model", help="Device model", required=True)
subparser = parser.add_subparsers(dest="command")
search = subparser.add_parser("search", help="Search for sources")
search.add_argument("-j", "--json", help="Return in JSON", action="store_true")
download = subparser.add_parser("download", help="Download source")
download.add_argument("-v", "--version", help="Source version", required=True)

args = parser.parse_args()
model = args.model

# Function: Find dict element of desired source from source version
def find_source_by_sourcever(dict_target, version):
    return next((item for i, item in enumerate(dict_target) if item["sourceVersion"] == str(version)), None)

# Initialize `requests` session
session = requests.Session()
session.verify = False

# Search query
# Access search page, get available `uploadId`,
# and store it in a dictionary along with `downloadPurpose`
requestSearch = session.get(searchURL + quote(model))
parseSearchContent = BeautifulSoup(requestSearch.content, "html.parser")
searchTable = parseSearchContent.find_all("table", class_="tbl-downList")
rowSearchTable = searchTable[0].find_all("tr", class_="")

dataList = []
for index, row in enumerate(rowSearchTable):
    dataSearchTable = row.find_all("td")

    sourceModel = dataSearchTable[1].text.strip()
    sourceVersion = dataSearchTable[2].text.strip()
    sourceUploadId = dataSearchTable[5].find("a")["href"].split("'")[1]

    dataList.append({
        "uploadId": sourceUploadId,
        "downloadPurpose": "AOP",
        "sourceVersion": sourceVersion,
        "sourceModel": sourceModel,
    })

# Command: "search"
# Do: Print data list
if args.command == "search":
    if args.json:
        print(json.dumps(dataList, indent=4))
    else:
        for index, data in enumerate(dataList):
            print(f"[{index + 1}] Model: {data['sourceModel']} | Version: {data['sourceVersion']}")

# Command: "download"
# Do: Download the source
if args.command == "download":
    selectedSource = find_source_by_sourcever(dataList, args.version)
    if not selectedSource:
        print("Invalid source version: " + args.version)
        exit(1)

    # Get remaining variable from modal page:
    # `attachIds`, `_csrf`, `token`
    requestModal = session.get(modalURL + selectedSource["uploadId"])
    parseModalRequest = BeautifulSoup(requestModal.content, "html.parser")

    selectedSource["attachIds"] = parseModalRequest.find_all("input", type="checkbox")[1]["id"]
    selectedSource["_csrf"] = parseModalRequest.find_all(attrs={"name": "_csrf"})[0]["value"]
    selectedSource["token"] = parseModalRequest.find_all(id="token")[0]["value"].encode("utf-8")

    # Download the source
    requestHeader = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36 Edg/99.0.1150.55",
    }
    requestDown = session.post(downSrcURL, data=selectedSource, headers=requestHeader, stream=True)
    sourceFileName = requestDown.headers["Content-Disposition"].split("=")[1][1:].replace('"', "").replace(";", "") # TODO: Better way of file name retrievement
    sourceSize = int(requestDown.headers["Content-Length"])

    try:
        print(f"Downloading {sourceFileName} ({selectedSource['sourceVersion']}), please do not terminate the script!")
        progressBar = tqdm(total=sourceSize, unit="B", unit_scale=True)
        with open(sourceFileName, "wb") as file:
            for chunk in requestDown.iter_content(chunk_size=512 * 1024):
                file.write(chunk)
                progressBar.update(len(chunk))
        progressBar.close()
        print("Done!")
    except KeyboardInterrupt:
        progressBar.close()
        os.remove(sourceFileName)
        print("Interrupted!")
        exit(130)
    except:
        progressBar.close()
        os.remove(sourceFileName)
        print("Error!")
        exit(1)

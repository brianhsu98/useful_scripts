import argparse
import glob
import json
import os


MT_SHARDS = os.path.expanduser("~/universe/mt-shards")
ENVIRONMENTS = ["dev", "staging", "prod"]
CLOUDS = ["azure", "aws", "gcp"]
IMPACTS = ["low", "medium", "high"]

def main(args):
    for environment in args.env:
        base_path = os.path.join(MT_SHARDS, environment)
        json_files = glob.glob(f"{base_path}/**/*.json", recursive=True)
        for json_file in json_files:
            with open(json_file) as f:
                shard_json = json.load(f)

            if shard_json["clusterType"] != "HomeGrownControlPlane" and not args.kaas:
                continue

            if shard_json["cloud"] not in args.cloud:
                continue

            if shard_json["environment"] not in args.env:
                continue

            if shard_json["environment"] != "dev":
                found = False
                for impact in args.impact:
                    shard_group = shard_json["serviceShardGroup"] 
                    if impact in shard_group.lower():
                        found = True
                if not found:
                    continue
                
            if not args.gfm:
                if "china" in shard_json["kubeContext"] or "gov" in shard_json["kubeContext"] or "fedramp" in shard_json["cloudEnvGroup"]:
                    continue

            print(shard_json["kubeContext"])





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process JSON files.")
    parser.add_argument("--env", type=str, nargs="+", choices=ENVIRONMENTS, default=ENVIRONMENTS)
    parser.add_argument("--cloud", type=str, nargs="+", choices=CLOUDS, default=CLOUDS)
    parser.add_argument("--impact", type=str, nargs="+", choices=IMPACTS, default=IMPACTS)
    parser.add_argument("--kaas", action="store_true")
    parser.add_argument("--gfm", action="store_true")
    main(parser.parse_args())

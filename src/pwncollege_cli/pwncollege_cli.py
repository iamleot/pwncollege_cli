#!/usr/bin/env python3


"""
CLI for pwn.college

pwncollege-cli is a script/module to interact with pwn.college directly
from a terminal.

It exposes the following subcommands:

- docker: start a challenge
- attempt: submit a flag
- status: show current pwn.college status (challenge/module/dojo selected)
- dojos: list all available dojos
- modules: list all available modules in a dojo
- challenges: list all available challanges of a module
- cookies: request and dump a session cookie

Both pwncollege-cli and each single command has a `-h` option for help,
please use it for the actual synopsis.
"""


from dataclasses import dataclass
from typing import Optional, Tuple
import argparse
import configparser
import getpass
import logging
import re
import os

import bs4
import requests

PWNCOLLEGE_CLI_BASE_URL = "https://pwn.college"
PWNCOLLEGE_CLI_USER_AGENT = "pwncollege_cli/0.0.1"


logger = logging.getLogger(__name__)


@dataclass
class Dojo:
    id: str
    name: str
    hacking: int
    modules: int
    challenges: int


@dataclass
class Module:
    id: str
    name: str
    hacking: int
    solved_challenges: int
    total_challenges: int


@dataclass
class Challenge:
    id: str
    name: str
    title: str
    description: str


class PwnCollegeCLI:
    def __init__(self, base_url: str = PWNCOLLEGE_CLI_BASE_URL):
        self.base_url = base_url
        self.logged_in = False
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": PWNCOLLEGE_CLI_USER_AGENT,
            }
        )

    def nonce(self) -> str:
        """Get a nonce.

        Refresh a nonce, i.e. just call the pwn.college base URL in order to
        get an usable (CSRF) nonce.

        Returns CSRF nonce.
        """
        logger.debug(f"Refreshing nonce via {self.base_url}")
        res = self.session.get(f"{self.base_url}")
        m = re.search(r"'csrfNonce': \"(?P<nonce>[^\"]+)\"", res.text)
        if not m:
            # FIXME: We should trow an exception in that case because nonce()
            # FIXME: is expected to never fail by its callers.
            logger.error("Could not retrieve CSRF nonce")
            return ""
        nonce = m.group("nonce")
        logger.debug(f"Retrieved nonce {nonce}")
        return nonce

    def login(
        self, username: str, password: str
    ) -> Optional[requests.models.Response]:
        """Login to pwn.college

        Given a username and password login to pwn.college.

        Internally it also set the logged_in attribute. The POST /login
        requests always return 200 also if incorrect credentials are passed
        but it sets the userId only if successfully logged in.

        Returns raw HTTP Response.
        """
        logger.debug(f"Logging in to {self.base_url} as {username}")

        res = self.session.get(f"{self.base_url}/login")

        res = self.session.post(
            f"{self.base_url}/login",
            data={
                "name": username,
                "password": password,
                "_submit": "Submit",
                "nonce": self.nonce(),
            },
        )

        # If we are successfully logged in the userId should be non-0.
        m = re.search(r"'userId': (?P<user_id>[0-9]+)", res.text)
        if not m:
            logger.error("Could not retrieve userId")
            return None
        user_id = m.group("user_id")
        self.logged_in = user_id != 0
        if self.logged_in:
            logger.debug(
                f"Successfully logged in {self.base_url} as {username}"
            )
        else:
            logger.error(f"Could not login to {self.base_url} as {username}")

        return res

    def cookies(self) -> Optional[str]:
        """Return session cookies.

        Print to stdout session cookies. Can be handy to manually interact with
        pwn.college outside pwncollege-cli.
        """
        logger.debug(f"Returning session cookies of {self.base_url}")

        if not self.logged_in:
            logger.warning(f"Not logged in to {self.base_url}, no cookies")

        return self.session.cookies.get("session")

    def logout(self) -> Optional[requests.models.Response]:
        """Logout from pwn.college

        Logout - if logged in - from pwn.college.

        Returns raw HTTP Response.
        """
        logger.debug(f"Logging out to {self.base_url}")

        if not self.logged_in:
            logger.warning(
                f"Not logged in to {self.base_url}, skipping logout"
            )
            return None

        # FIXME: Wrongly assumes that we are always able to logout...
        # FIXME: `logged_in` instead of being an attribute it should do a
        # FIXME: `GET /` and check the `userId` everytime. Like it does in
        # FIXME: `login()`.
        res = self.session.get(f"{self.base_url}/logout")
        self.logged_in = False
        return res

    def docker(
        self, challenge: str, dojo: str, module: str, practice: bool = False
    ) -> requests.models.Response:
        """Start a challenge.

        Start Docker container challenge given challenge name, dojo,
        module.

        If practice boolean is set to True the challenge will be
        started in practice mode.

        Returns raw HTTP Response.
        """
        logger.debug(
            f"Starting Docker for challenge {challenge} for dojo "
            + f"{dojo} in module {module}"
        )

        self.session.headers.update(
            {
                "csrf-token": self.nonce(),
            }
        )
        res = self.session.post(
            f"{self.base_url}/pwncollege_api/v1/docker",
            json={
                "challenge": challenge,
                "dojo": dojo,
                "module": module,
                "practice": practice,
            },
        )
        del self.session.headers["csrf-token"]

        return res

    def attempt(
        self, challenge_id: int, flag: str
    ) -> requests.models.Response:
        """Attempt to submit a flag for challenge ID.

        Submit a flag for challenge_id.

        Returns raw HTTP Response.
        """
        logger.debug(f"Submitting flag {flag} for challenge ID {challenge_id}")

        self.session.headers.update(
            {
                "csrf-token": self.nonce(),
            }
        )
        res = self.session.post(
            f"{self.base_url}/api/v1/challenges/attempt",
            json={
                "challenge_id": challenge_id,
                "submission": flag,
            },
        )
        del self.session.headers["csrf-token"]

        return res

    def status(self) -> requests.models.Response:
        """Show current Docker status.

        Print out possible current selected challenge.

        Returns raw HTTP Response.
        """
        logger.debug("Requesting current Docker status")

        self.session.headers.update(
            {
                "csrf-token": self.nonce(),
            }
        )
        res = self.session.get(f"{self.base_url}/pwncollege_api/v1/docker")
        del self.session.headers["csrf-token"]

        return res

    @staticmethod
    def _parse_dojos(response: requests.models.Response) -> list[Dojo]:
        """Parse response of dojos and return list of Dojo.

        Returns a list of Dojo.
        """
        dojos = []
        b = bs4.BeautifulSoup(response.content, "html.parser")
        for e in b.find_all("a", href=re.compile(r"/dojo/")):
            assert isinstance(e, bs4.element.Tag)
            assert isinstance(e["href"], str)

            dojo_id = e["href"].removeprefix("/dojo/")

            card_title = e.find(class_="card-title")
            if not card_title:
                break
            dojo_name = card_title.text

            card_text = e.find(class_="card-text")
            if not card_text:
                break

            hacking = 0  # noone could be hacking on dojo
            for s in card_text.stripped_strings:
                if "Hacking" in s:
                    hacking = int(s.split()[0])
                    continue
                if "Modules" in s:
                    modules = int(s.split()[0])
                    continue
                if "Challenges" in s:
                    challenges = int(s.split()[0])
                    continue

            dojos.append(
                Dojo(
                    id=dojo_id,
                    name=dojo_name,
                    hacking=hacking,
                    modules=modules,
                    challenges=challenges,
                )
            )
        return dojos

    def dojos(self) -> list[Dojo]:
        """Show all dojos.

        Returns raw HTTP Response.
        """
        logger.debug("Requesting dojos")
        res = self.session.get(f"{self.base_url}/dojos")
        return self._parse_dojos(res)

    @staticmethod
    def _parse_modules(
        response: requests.models.Response, dojo: str
    ) -> list[Module]:
        """Parse response of modules and return list of Module.

        Returns a list of Module.
        """
        modules = []
        b = bs4.BeautifulSoup(response.content, "html.parser")
        for e in b.find_all("a", href=re.compile(f"^/{dojo}/[a-z0-9-]+/?$")):
            assert isinstance(e, bs4.element.Tag)
            assert isinstance(e["href"], str)

            module_id = e["href"].removeprefix(f"/{dojo}/").removesuffix("/")

            card_title = e.find(class_="card-title")
            if not card_title:
                break
            module_name = card_title.text

            card_text = e.find(class_="card-text")
            if not card_text:
                break

            hacking = 0  # noone could be hacking on module
            for s in card_text.stripped_strings:
                if "Hacking" in s:
                    hacking = int(s.split()[0])
                    continue
                if " / " in s:
                    solved_challenges, total_challenges = (
                        int(n) for n in s.split(" / ")
                    )
                    continue

            modules.append(
                Module(
                    id=module_id,
                    name=module_name,
                    hacking=hacking,
                    solved_challenges=solved_challenges,
                    total_challenges=total_challenges,
                )
            )
        return modules

    def modules(self, dojo: str) -> list[Module]:
        """Show all modules in a dojo.

        Returns raw HTTP Response.
        """
        logger.debug(f"Requesting modules in dojo {dojo}")
        res = self.session.get(f"{self.base_url}/{dojo}/")
        return self._parse_modules(res, dojo)

    @staticmethod
    def _parse_challenges(
        response: requests.models.Response,
    ) -> list[Challenge]:
        """Parse response of challenges and return list of Challenge.

        Returns a list of Challenge.
        """
        challenges = []
        b = bs4.BeautifulSoup(response.content, "html.parser")
        for header, body in zip(
            b.find_all("div", id=re.compile("challenges-header")),
            b.find_all("div", id=re.compile("challenges-body")),
        ):
            assert isinstance(body, bs4.element.Tag)
            assert isinstance(header, bs4.element.Tag)

            t = body.find("input", id="challenge-id")
            assert isinstance(t, bs4.element.Tag)
            challenge_id = t["value"]
            assert isinstance(challenge_id, str)

            t = body.find("input", id="challenge")
            assert isinstance(t, bs4.element.Tag)
            challenge_name = t["value"]
            assert isinstance(challenge_name, str)

            t = header.find("h4", class_="challenge-name")
            assert isinstance(t, bs4.element.Tag)
            challenge_title = t.text.strip()

            t = body.find("div", class_="embed-responsive")
            assert isinstance(t, bs4.element.Tag)
            challenge_description = t.text.strip()

            challenges.append(
                Challenge(
                    id=challenge_id,
                    name=challenge_name,
                    title=challenge_title,
                    description=challenge_description,
                )
            )
        return challenges

    def challenges(self, dojo: str, module: str) -> list[Challenge]:
        """Show all challenges in a dojo module.

        Returns raw HTTP Response.
        """
        logger.debug(
            f"Requesting challenges in dojo {dojo} for module {module}"
        )
        res = self.session.get(f"{self.base_url}/{dojo}/{module}")
        return self._parse_challenges(res)


def credentials() -> Tuple[str, str]:
    """Read pwn.college credentials.

    Parse `~/.pwncollege_cli` configuration file and return credentials
    (username and password).

    If no configuration file is found or could not be parsed fallback to
    interactively ask the user the credentials.

    Returns username and password.
    """
    try:
        cp = configparser.ConfigParser()
        cp.read(os.path.expanduser("~/.pwncollege_cli"))
        if cp["pwn.college"].get("name"):
            username = cp["pwn.college"]["name"]
        if cp["pwn.college"].get("passwordeval"):
            password = (
                os.popen(cp["pwn.college"]["passwordeval"]).read().rstrip("\n")
            )
        if cp["pwn.college"].get("password"):
            password = cp["pwn.college"]["password"]
    except Exception:
        username = input("username or email: ")
        password = getpass.getpass("password: ")

    return username, password


def _argument_parser() -> argparse.ArgumentParser:
    """
    Construct the argument parser.

    Returns an ArgumentParser.
    """
    ap = argparse.ArgumentParser(
        prog="pwncollege-cli",
        description="Interact with pwn.college from a CLI",
    )
    sp = ap.add_subparsers(dest="subcommand", help="subcommand", required=True)

    dockerp = sp.add_parser("docker", help="start Docker container")
    dockerp.add_argument(
        "-c",
        type=str,
        dest="challenge",
        help="challenge name",
        required=True,
    )
    dockerp.add_argument(
        "-d",
        type=str,
        dest="dojo",
        help="dojo name",
        required=True,
    )
    dockerp.add_argument(
        "-m",
        type=str,
        dest="module",
        help="module name",
        required=True,
    )
    dockerp.add_argument(
        "-p",
        action="store_true",
        dest="practice",
        help="start in practice mode",
    )

    attemptp = sp.add_parser("attempt", help="submit a flag")
    attemptp.add_argument(
        "-c",
        type=int,
        dest="challenge_id",
        help="challenge ID",
        required=True,
    )
    attemptp.add_argument(
        "-f",
        type=str,
        dest="flag",
        help="flag",
        required=True,
    )

    sp.add_parser("status", help="show Docker container status")

    sp.add_parser("dojos", help="show dojos")

    modules = sp.add_parser("modules", help="show modules")
    modules.add_argument(
        "-d",
        type=str,
        dest="dojo",
        help="dojo name",
        required=True,
    )

    challenges = sp.add_parser("challenges", help="show challenges")
    challenges.add_argument(
        "-d",
        type=str,
        dest="dojo",
        help="dojo name",
        required=True,
    )
    challenges.add_argument(
        "-m",
        type=str,
        dest="module",
        help="module name",
        required=True,
    )

    sp.add_parser("cookies", help="show cookies")
    return ap


def main() -> None:
    log = logging.getLogger(__name__)
    log.setLevel(logging.INFO)
    log.addHandler(logging.StreamHandler())

    argument_parser = _argument_parser()
    args = argument_parser.parse_args()

    pcc = PwnCollegeCLI()
    username, password = credentials()
    pcc.login(username, password)
    if args.subcommand == "docker":
        pcc.docker(
            challenge=args.challenge,
            dojo=args.dojo,
            module=args.module,
            practice=args.practice,
        )
        pcc.logout()
    elif args.subcommand == "attempt":
        pcc.attempt(challenge_id=args.challenge_id, flag=args.flag)
        pcc.logout()
    elif args.subcommand == "status":
        res = pcc.status()
        j = res.json()
        if j["success"]:
            logger.info(
                "Currently running Docker container "
                + f"challenge: {j['challenge']}, module: {j['module']}, "
                + f"dojo: {j['dojo']}"
            )
        else:
            logger.error(f"Could not get status: {j['error']}")
        pcc.logout()
    elif args.subcommand == "dojos":
        for dojo in pcc.dojos():
            logger.info(
                f"{dojo.id}: {dojo.name} "
                + "("
                + f"{dojo.hacking} Hacking, "
                + f"{dojo.modules} Modules, "
                + f"{dojo.challenges} Challenges)"
            )
        pcc.logout()
    elif args.subcommand == "modules":
        for module in pcc.modules(dojo=args.dojo):
            logger.info(
                f"{module.id}: {module.name} "
                + "("
                + f"{module.hacking} Hacking, "
                + f"{module.solved_challenges} / "
                + f"{module.total_challenges} Challenges)"
            )
        pcc.logout()
    elif args.subcommand == "challenges":
        for challenge in pcc.challenges(dojo=args.dojo, module=args.module):
            logger.info(
                f"{challenge.id} - {challenge.name}: {challenge.title}\n"
                + f"{challenge.description}"
            )
        pcc.logout()
    elif args.subcommand == "cookies":
        cookies = pcc.cookies()
        if not cookies:
            logger.error("Could not get session cookies.")
        logger.info(f"Session cookies: {cookies}")


if __name__ == "__main__":
    main()

# pwncollege_cli

`pwncollege_cli` is a script/module to interact with pwn.college directly
from a terminal.

It exposes the following subcommands:

- docker: start a challenge
- attempt: submit a flag
- status: show current pwn.college status (challenge/module/dojo selected)
- dojos: list all available dojos
- modules: list all available modules in a dojo
- challenges: list all available challanges of a module
- cookies: request and dump a session cookie

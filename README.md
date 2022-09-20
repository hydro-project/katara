<h1 align="center">Katara</h1>
<p align="center"><i>Synthesize CRDTs that mirror your existing data types!</i></p>

Katara is a program synthesis engine that can automatically generate CRDT designs that match the behavior of a sequential data type annotated with a conflict resolution policy for non-commutative operations. See our [paper](https://arxiv.org/pdf/2205.12425.pdf) for more information!

## Setup
### Install (with Nix)
To get a development environment up and running, one option is to use [Nix](https://nixos.org/), which can automatically pull and build the necessary dependencies. First, you'll need to [install Nix](https://nixos.org/download.html). Note that this _will_ require temporary root access as Nix sets up a daemon to handle builds, and will set up a separate volume for storing build artifacts if on macOS.

Once you've got Nix installed, you'll need to add the unstable channel to pull bleeding-edge packages as dependencies for cvc5.

```bash
# if on macOS
$ sudo -i nix-channel --add https://nixos.org/channels/nixos-unstable nixos-unstable
$ sudo -i nix-channel --update

# otherwise
$ sudo nix-channel --add https://nixos.org/channels/nixos-unstable nixos-unstable
$ sudo nix-channel --update
```

Then, all you have to do is navigate to the Metalift directory and run the following command:
```bash
$ nix-shell
```

This will build all of Metalift's dependencies and drop you into a temporary shell with all the dependencies available.

**Note**: you still will need to install Racket and Rosette separately. There _is_ a solution for doing this through Nix, but it requires [nix-ld](https://github.com/Mic92/nix-ld) to be installed and is generally not recommended unless you run NixOS.

### Install (without Nix)
You'll need the following dependencies installed to use Katara:
- Python 3.8 with Poetry
- [Rosette](https://emina.github.io/rosette)
- [CVC5](https://cvc5.github.io)
- [LLVM 11](https://llvm.org/)

We use [Poetry](https://python-poetry.org/) for dependency management. To set up the environment, simply install Poetry, run `poetry install`, and then `poetry shell` to enter an environment with the dependencies installed.

### Build the LLVM Pass

**We currently support LLVM 11**

Run the following to build the LLVM pass for processing branch instructions (works for LLVM 11):
````angular2
cd llvm-pass
mkdir build
cd build
cmake ..
make 
cd ..
```` 
Then run it with:
````angular2
opt -load build/addEmptyBlocks/libAddEmptyBlocksPass.so -addEmptyBlock -S <.ll name>
````
This pass is called in `tests/compile-add-blocks`.

## Synthesizing CRDTs
The first step to synthesizing a CRDT is to compile the sequential reference. We have provided a set of benchmark sequential data types in the `tests/` folder. These can be compiled by entering the folder and running `compile-all`:
```bash
$ cd tests
$ ./compile-all
```

Then, from the base directory of the project, we can run the synthesis benchmarks defined in `tests/synthesize_crdt.py` (in the `benchmarks` variable). Each benchmark is configured with the sequential data type to process, the ordering constraing as defined in our paper (`opOrder`), flags to enable synthesis of non-idempotent operations, and type hints to optimize the synthesis process. With a benchmark configured, we can run it as
```bash
$ python -m tests.synthesize_crdt synth <BENCHMARK NAME>
```

For example, we can synthesize for the 2P-Set benchmark with
```bash
$ python -m tests.synthesize_crdt synth 2p_set
```

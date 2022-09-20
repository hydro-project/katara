import sys
import pandas
import matplotlib.pyplot as plt

if __name__ == "__main__":
    bench = sys.argv[1]
    first_n = int(sys.argv[2].split("first_")[1])

    no_pruning = pandas.read_csv(f"benchmarks-{bench}-direct-unbounded-first_{first_n}-distribution.csv")
    no_pruning["time"] = no_pruning["time"] / 60
    bounded_history = pandas.read_csv(f"benchmarks-{bench}-bounded-pruning-first_{first_n}-distribution.csv")
    bounded_history["time"] = bounded_history["time"] / 60

    plt.figure()
    ax = bounded_history.plot(x="time",y="percent",label="bounded history")
    no_pruning.plot(x="time",y="percent",label="direct unbounded",ax=ax)
    ax.set_xlabel("Synthesis Time (minutes)")
    ax.set_ylabel("Candidates Evaluated")
    plt.legend(loc='lower right')

    plt.savefig(f"distribution-{bench}-first_{first_n}.png")
    plt.show()

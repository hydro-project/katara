#include <map>
#include "llvm/Pass.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/LegacyPassManager.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/Transforms/IPO/PassManagerBuilder.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/Transforms/Utils/BasicBlockUtils.h"

using namespace llvm;

namespace 
{
  /*
   Add empty BBs after all conditional branches to ensure that there is always a "else" BB.
   The idea is to transform a CFG like:

        /---------\
   b1 -----> b2-----> b3

   into:

        /----b4----------\
   b1 -----> b5 ---> b2 -----> b3

   To do so we need to do two things:
   1. add new blocks b4 and b5 and make them the successors of b1
   2. change all PHI nodes in the original successors of the two branches such that they
      point to the newly created BBs as their predecessors instead
   */
  struct AddEmptyBlockPass : public FunctionPass 
  {
    static char ID;
    AddEmptyBlockPass() : FunctionPass(ID) {}

    BasicBlock *createBB(Function &F, BasicBlock * succ) 
    {
      auto * bb = BasicBlock::Create(F.getContext(), "", &F);
      IRBuilder<> builder(bb);
      builder.CreateBr(succ);
      return bb;
    }

    virtual bool runOnFunction(Function &F) 
    {
      std::map<BranchInst*, BranchInst*> toReplace;

      for (auto &B : F) 
      {
        for (auto &I : B) 
        {
          if (auto *op = dyn_cast<BranchInst>(&I))
          {
            if (op->isConditional())
            {
              BasicBlock * trueBB = createBB(F, op->getSuccessor(0));
              BasicBlock * falseBB = createBB(F, op->getSuccessor(1));

              op->getSuccessor(0)->replacePhiUsesWith(&B, trueBB);
              op->getSuccessor(1)->replacePhiUsesWith(&B, falseBB);

              BranchInst *br = BranchInst::Create(trueBB, falseBB, op->getCondition());
              toReplace.insert(std::pair<BranchInst*, BranchInst*>(op, br));
            }            
          }
        }
      }

      for (auto &kv : toReplace) 
      {
        if (!kv.first->use_empty())
          kv.first->replaceAllUsesWith(kv.second);
        errs() << "replace: " << *kv.first << " with " << *kv.second << "\n";
        ReplaceInstWithInst(kv.first, kv.second); 
      }

      return toReplace.size();
    }
  };
}

char AddEmptyBlockPass::ID = 0;

static RegisterPass<AddEmptyBlockPass> X("addEmptyBlock", "Add empty blocks for conditionals pass",
                             false /* Only looks at CFG */,
                             false /* Analysis Pass */);

static RegisterStandardPasses Y(
    PassManagerBuilder::EP_EarlyAsPossible,
    [](const PassManagerBuilder &Builder,
       legacy::PassManagerBase &PM) {
        PM.add(new AddEmptyBlockPass());
       });

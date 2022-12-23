
class StaticMemoryAllocation():

    def __init__(self, global_vars: dict(), global_vars_const: list(), global_vars_priv: list(), results_arrays: list()) -> None:
        self.__global_vars: dict() = global_vars
        self.__global_vars_const = global_vars_const
        self.__global_vars_priv = global_vars_priv
        self.__results_arrays = results_arrays

    def generate(self):
        print('; Allocating Global (static) memory')
        for n in self.__global_vars:
            print(f'{str(n+":"):<9}\t.BLOCK 2') # reserving memory

        for n in self.__global_vars_const:
            print(f'{str(n[0]+":"):<9}\t.WORD {n[1]}') # allocating constant value to memory, n[0] is the var name, n[1] is const val

        for n in self.__global_vars_priv:
            print(f'{str(n[0]+":"):<9}\t.EQUATE {n[1]}') # allocating constant value to memory, n[0] is the var name, n[1] is const val

        for n in self.__results_arrays: 
            print(f'{str(n[0]+":"):<9}\t.BLOCK {n[1].value*2}') # allocating constant value to memory, n[0] is the var name, n[1] is const val
 
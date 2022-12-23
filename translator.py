import argparse
import ast
from visitors.GlobalVariables import GlobalVariableExtraction
from visitors.TopLevelProgram import TopLevelProgram
from visitors.FuncDef import FuncDef
from generators.StaticMemoryAllocation import StaticMemoryAllocation
from generators.EntryPoint import EntryPoint

def main():
    input_file, print_ast = process_cli()
    with open(input_file) as f:
        source = f.read()
    node = ast.parse(source)
    if print_ast:
        print(ast.dump(node, indent=2))
    else:
        process(input_file, node)
    
def process_cli():
    """"Process Command Line Interface options"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', help='filename to compile (.py)')
    parser.add_argument('--ast-only', default=False, action='store_true')
    args = vars(parser.parse_args())
    return args['f'], args['ast_only']

def process(input_file, root_node):
    print(f'; Translating {input_file}')
    extractor = GlobalVariableExtraction()
    extractor.visit(root_node)
    memory_alloc = StaticMemoryAllocation(extractor.results, extractor.results_const, extractor.results_priv, extractor.results_arrays)
    print('; Branching to top level (tl) instructions')
    print('\t\tBR tl')
    memory_alloc.generate()
    # function definitions
    func_level = FuncDef(extractor.name_mapping)
    # visit all func defn nodes
    for i in root_node.body:
        if (isinstance(i, ast.FunctionDef)):
            func_level.visit(i)
    ep_f = EntryPoint(func_level.finalize())
    ep_f.generate_f()


    top_level = TopLevelProgram('tl', extractor.name_mapping, func_level.actual_arguments, func_level.ret_name)
    top_level.visit(root_node)
    ep = EntryPoint(top_level.finalize())
    ep.generate() 

if __name__ == '__main__':
    main()

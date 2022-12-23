import ast
import random
import string

class GlobalVariableExtraction(ast.NodeVisitor):
    """ 
        We extract all the left hand side of the global (top-level) assignments
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.results = set()        # Non-Constant assignments
        self.results_const = []     # Constant assignments, n[0] is the var name and n[1] is const val
        self.results_priv = []      # Constant private var
        self.results_arrays = []
        self.names = {}
        self.array_names = {}


        # store mapping of old names to new shortened names
        self.name_mapping = {}

    def visit_Assign(self, node):
        if len(node.targets) != 1:
            raise ValueError("Only unary assignments are supported")

        
        if isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            old_name = name
        
        elif isinstance (node.targets[0], ast.Subscript):
            name = node.targets[0].value.id 
            

        # Ensure legal var length
        if len(name) > 8: 
            name = name[:8]
            while name in self.names:
                index = random.randint(1,len(name))
                newchar = random.choice(string.ascii_letters)
                # change random chacter in name to get unique name
                name = name[:index] + newchar + name[index + 1:] 
            
            self.name_mapping[old_name] = name

        # check if the assignment is to an array 
        if name[-1] == '_':
            if self.results_arrays:
                for i in self.results_arrays:
                    if name not in i[0]:
                        self.results_arrays.append([name, node.value.right])
            else: 
                self.results_arrays.append([name, node.value.right])
    
        
        if isinstance(node.value, ast.Constant):    # Check if value being assigned is a constant
            if name[0] == '_' and name[1:].isupper:        # Check if var is private
                if name not in self.names:
                    self.names[name] = True
                    self.results_priv.append([name, node.value.value])
            else:
                if name not in self.names:
                    self.names[name] = True
                    self.results_const.append([name, node.value.value])
        else:
            if name not in self.names:
                inside = False
                for i in self.results_arrays: 
                    if name == i[0]:
                        inside = True
                if inside == False: 
                    self.names[name] = True
                    self.results.add(name)


    def visit_FunctionDef(self, node):
        """We do not visit function definitions, they are not global by definition"""
        pass
   
import ast

LabeledInstruction = tuple[str, str]

class TopLevelProgram(ast.NodeVisitor):
    """We supports assignments and input/print calls"""
    
    def __init__(self, entry_point, name_mapping, actual_arguments = None, ret_name = None) -> None:
        super().__init__()
        self.__instructions = list()
        self.__record_instruction('NOP1', label=entry_point)
        self.__should_save = True
        self.__current_variable = None
        self.__elem_id = 0
        self.ret_name =ret_name

        #var names, True means it has been used and so must be reassigned
        self.names = {}

        # name mapping for long var names from GlobalVariables.py
        self.name_mapping = name_mapping

        # check if an assignment involves a func call, to know if need to increase stack size
        self.has_call = False

        self.actual_loc_vars = {}
        self.actual_arguments = actual_arguments

    def finalize(self):
        if self.ret_name:
             self.__instructions.append((None,"ADDSP 2,i"))
            
        self.__instructions.append((None, '.END'))
        return self.__instructions

    ####
    ## Handling Assignments (variable = ...)
    ####

    def visit_Assign(self, node):
        # remembering the name of the target
        if isinstance(node.targets[0], ast.Name):
            self.__current_variable = node.targets[0].id
        
        elif isinstance (node.targets[0], ast.Subscript):
            self.__current_variable = node.targets[0].value.id 
        

        # check if there is a func call
        if isinstance(node.value, ast.Call):
            self.has_call = True

        # # if assignment value is constant, already stored as a global variable so no need to assign
        if isinstance(node.value, ast.Constant):
            # private nodes do not need to be assigned
            if isinstance(node.targets[0], ast.Name):
                if self.isPrivate(node.targets[0].id): 
                    return
            
                # if assigning constant for the first time, skip
                if node.targets[0].id not in self.names:
                    self.names[node.targets[0].id] = True
                    return
                

        # visiting the left part, now knowing where to store the result
        self.visit(node.value)
        if self.__should_save:
            if self.__current_variable[-1] == '_':
                pass
            else:
                self.__record_instruction(f'STWA {self.__current_variable},d')
        else:
            self.__should_save = True
        self.__current_variable = None

        # if self.has_call:
        #     self.__record_instruction(f'ADDSP 2,i')
        self.has_call = False

    def visit_Constant(self, node):
        self.__record_instruction(f'LDWA {node.value},i')
    
    def visit_Name(self, node):
        # check if id is too long, get name from dict
        if len(node.id) > 8:
            self.__record_instruction(f'LDWA {self.name_mapping[node.id]},d')
        else:
            self.__record_instruction(f'LDWA {node.id},d')

    def visit_BinOp(self, node):
        self.__access_memory(node.left, 'LDWA')
        if isinstance(node.op, ast.Add):
            self.__access_memory(node.right, 'ADDA')
        elif isinstance(node.op, ast.Sub):
            self.__access_memory(node.right, 'SUBA')
        elif isinstance(node.op, ast.Mult):
            return
        else:
            raise ValueError(f'Unsupported binary operator: {node.op}')

    def visit_Call(self, node):
        match node.func.id: 
            case 'int': 
                # Let's visit whatever is casted into an int
                self.visit(node.args[0])
            case 'input':
                # We are only supporting integers for now
                if self.__current_variable[-1] == '_':
                    self.__record_instruction(f'DECI {self.__current_variable},x')
                else:
                    self.__record_instruction(f'DECI {self.__current_variable},d')
                self.__should_save = False # DECI already save the value in memory
            case 'print':
                # We are only supporting integers for now
                if isinstance(node.args[0], ast.Subscript):
                    self.__record_instruction(f'DECO {node.args[0].value.id}, x')
                else:
                   self.__record_instruction(f'DECO {node.args[0].id},d')
            case _:
                # count num of args
                count_args = 0
                count_call = 0



                for i in node.args:
                    count_args += 2
                    
                if self.has_call:
                    count_call += 2
                


                if count_args + count_call > 0:
                    st = ""
                    for i in self.actual_arguments.values():
                        st = st + ("#"+i+" ")
                    self.__record_instruction(f'SUBSP {count_args + count_call},i\t ; push {st}')

                c = 0
                for i in node.args:
                    self.visit(i)
                    self.__record_instruction(f'STWA {c},s')
                    c+= 2
                self.__record_instruction(f'CALL {node.func.id}')
                
                if count_args > 0:
                    st = ""
                    for i in self.actual_arguments.values():
                        st = st + ("#"+i+" ")
                    self.__record_instruction(f'ADDSP {count_args},i\t ; pop {st}')
                
                if count_call > 0:
                    self.__record_instruction(f'LDWA 0,s')
                


    ####
    ## Handling While loops (only variable OP variable)
    ####

    def visit_While(self, node):
        b = False
        loop_id = self.__identify()
        inverted = {
            ast.Lt:  'BRGE', # '<'  in the code means we branch if '>=' 
            ast.LtE: 'BRGT', # '<=' in the code means we branch if '>' 
            ast.Gt:  'BRLE', # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT', # '>=' in the code means we branch if '<'
            ast.Eq: 'BRNE', # '==' in the code means we branch if '!='
            ast.NotEq: 'BREQ', # '!=' in the code means we branch if '=='
        }
        for content in node.body:
            if isinstance(content, ast.Expr):
                if isinstance(content.value, ast.Call):
                    for i in content.value.args: 
                        if isinstance(i, ast.Subscript):
                            b = True
        if b == True: 
            # left part can only be a variable
            self.__access_memory(node.test.left, 'LDWX', label = f'test_l_{loop_id}')
            # right part can only be a variable
            self.__access_memory(node.test.comparators[0], 'CPWX')
        else:
            # left part can only be a variable
            self.__access_memory(node.test.left, 'LDWA', label = f'test_l_{loop_id}')
            # right part can only be a variable
            self.__access_memory(node.test.comparators[0], 'CPWA')

        # Branching is condition is not true (thus, inverted)
        self.__record_instruction(f'{inverted[type(node.test.ops[0])]} end_l_{loop_id}')
        # Visiting the body of the loop
        for contents in node.body:
            # if there is an assignment using a constant, never skip it in a while loop
            if isinstance(contents, ast.Assign):
                # if isinstance(contents.targets[0], ast.Name):
                    if isinstance(contents.value, ast.Constant):
                        self.names[contents.targets[0].id] = True

            self.visit(contents)
        self.__record_instruction(f'BR test_l_{loop_id}')
        # Sentinel marker for the end of the loop
        self.__record_instruction(f'NOP1', label = f'end_l_{loop_id}')

    ####
    ## Handling conditional statements
    ####
    def visit_If(self, node): 
        cond_id = self.__identify()
        inverted = {
            ast.Lt:  'BRGE', # '<'  in the code means we branch if '>=' 
            ast.LtE: 'BRGT', # '<=' in the code means we branch if '>' 
            ast.Gt:  'BRLE', # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT', # '>=' in the code means we branch if '<'
            ast.Eq: 'BRNE', # '==' in the code means we branch if '!='
            ast.NotEq: 'BREQ', # '!=' in the code means we branch if '=='
        }

        self.__access_memory(node.test.left, 'LDWA', label = f'test_i_{cond_id}')
        self.__access_memory(node.test.comparators[0], 'CPWA')

        self.__record_instruction(f'{inverted[type(node.test.ops[0])]} else_{cond_id}')
        for contents in node.body:
            
            # if there is an assignment using a constant, never skip it in a loop
            if isinstance(contents, ast.Assign):
                if isinstance(contents.value, ast.Constant):
                    self.names[contents.targets[0].id] = True

            self.visit(contents)
        self.__record_instruction(f'BR end_if_{cond_id}')
        self.__record_instruction(f'NOP1', label = f'else_{cond_id}')
        for contents in node.orelse: 
            self.visit(contents)
        self.__record_instruction(f'BR end_if_{cond_id}')
        self.__record_instruction(f'NOP1', label = f'end_if_{cond_id}')

    ####
    ## Not handling function calls 
    ####

    def visit_FunctionDef(self, node):
        """We do not visit function definitions, they are not top level"""
        pass

    ####
    ## Helper functions to 
    ####

    def __record_instruction(self, instruction, label = None):
        self.__instructions.append((label, instruction))

    def __access_memory(self, node, instruction, label = None):
        
        if isinstance(node, ast.Constant):
            self.__record_instruction(f'{instruction} {node.value},i', label)
            return
        # if var name is too long    
        if isinstance(node, ast.List):
            return

        if isinstance(node, ast.Assign):
            if isinstance(node.targets[0], ast.Subscript):
                if self.isArray(node):
                    self.__record_instruction(f'{instruction} {node.targets[0].value.id}, x', label)
            return 

        # if var name is too long
        if len(node.id) > 8:
            name = self.name_mapping[node.id]
        else:
            name = node.id

        # if accessing a private variable
        if self.isPrivate(node.id):
            self.__record_instruction(f'{instruction} {name},i', label)
        else:
            self.__record_instruction(f'{instruction} {name},d', label)


    def __identify(self):
        result = self.__elem_id
    
        self.__elem_id = self.__elem_id + 1
        return result

    # find if variable name is private
    def isPrivate(self, nodeName):
        if nodeName[0] == '_' and nodeName[1:].isupper:
            return True
        return False

    def isArray(self, node):
        for contents in node.body:
            if isinstance(contents, ast.Assign):
                for target in contents.targets:
                    if isinstance(target, ast.Subscript):
                        return True 
        return False 
        
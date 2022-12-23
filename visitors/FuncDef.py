import ast

LabeledInstruction = tuple[str, str]

class FuncDef(ast.NodeVisitor):
    
    def __init__(self, name_mapping) -> None:
        super().__init__()
        self.__instructions = list()
        # self.__record_instruction('NOP1', label=entry_point)
        self.__should_save = True
        self.__current_variable = None
        self.__elem_id = 0


        # collect all function defenition nodes in AST
        self.func_nodes = []


        #var names, True means it has been used and so must be reassigned
        self.names = {}

        # name mapping for long var names from GlobalVariables.py
        self.name_mapping = name_mapping

        # every function call will store it's local vars/params/ret stack addresses here, then wipe it when complete
        self.temp_loc_vars = {}
        self.func_def = False

        self.actual_loc_vars = {}
        self.actual_arguments = {}

        # check if an assignment involves a func call, to know if need to increase stack size
        self.has_call = False
        self.ret_name = None


    def pre_finalize(self):
        if self.ret_name:
            self.__record_instruction(f'STWA {self.ret_name[0:1]}ret,s')


        if self.temp_loc_vars:
            st = ""
            for i in self.actual_loc_vars.values():
                st = st + ("#"+i+" ")
            self.__record_instruction(f'ADDSP {len(self.actual_loc_vars)*2},i\t ;pop {st}')
        self.__instructions.append((None, 'RET'))
                # clearing the temp_vars dict
        self.actual_loc_vars.clear()
        

    def finalize(self):
        # self.temp_loc_vars.clear()
        return self.__instructions

    ####
    ## Handling Assignments (variable = ...)
    ####

    def visit_Assign(self, node):
        # remembering the name of the target
        self.__current_variable = node.targets[0].id
        func_def_var = False

        # check if we are assigning to a function local var
        if self.__current_variable in self.temp_loc_vars:
            func_def_var = True

        # # if assignment value is constant, already stored as a global variable so no need to assign
        if isinstance(node.value, ast.Constant):
            # private nodes do not need to be assigned
            if self.isPrivate(node.targets[0].id): 
                return
            
        # check if there is a func call
            if isinstance(node.value, ast.Call):
                self.has_call = True


        # visiting the left part, now knowing where to store the result
        self.visit(node.value)
        if self.__should_save:
            if func_def_var:
                self.__record_instruction(f'STWA {self.temp_loc_vars[self.__current_variable]},s')
            else:
                self.__record_instruction(f'STWA {self.__current_variable},d')
        else:
            self.__should_save = True
        self.__current_variable = None
        
        if self.has_call:
            self.__record_instruction(f'ADDSP 2,i')
        self.has_call = False

    def visit_Constant(self, node):
        self.__record_instruction(f'LDWA {node.value},i')
    
    def visit_Name(self, node):
        # check if id is too long, get name from dict
        if len(node.id) > 8:
            self.__record_instruction(f'LDWA {self.name_mapping[node.id]},d')
        else:
            if node.id in self.temp_loc_vars:
                self.__record_instruction(f'\t\tLDWA {self.temp_loc_vars[node.id]},s')
            else:
                self.__record_instruction(f'LDWA {node.id},d')

    def visit_BinOp(self, node):
        self.__access_memory(node.left, 'LDWA')
        if isinstance(node.op, ast.Add):
            self.__access_memory(node.right, 'ADDA')
        elif isinstance(node.op, ast.Sub):
            self.__access_memory(node.right, 'SUBA')
        else:
            raise ValueError(f'Unsupported binary operator: {node.op}')

    def visit_Call(self, node):
        match node.func.id: 
            case 'int': 
                # Let's visit whatever is casted into an int
                self.visit(node.args[0])
            case 'input':
                # We are only supporting integers for now
                if self.__current_variable in self.temp_loc_vars:
                    self.__record_instruction(f'DECI {self.temp_loc_vars[self.__current_variable]},s')
                else:
                    self.__record_instruction(f'DECI {self.__current_variable},d')
                self.__should_save = False # DECI already save the value in memory
            case 'print':
                # We are only supporting integers for now
                if node.args[0].id in self.temp_loc_vars:
                    self.__record_instruction(f'DECO {self.temp_loc_vars[node.args[0].id]},s')
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
                self.__record_instruction(f'SUBSP {count_args + count_call},i')

                c = 0
                for i in node.args:
                    self.visit(i)
                    self.__record_instruction(f'STWA {c},s')
                    c+= 2
                self.__record_instruction(f'CALL {node.func.id}')
                
                if count_args > 0:
                    self.__record_instruction(f'ADDSP {count_args},i')
                
                if count_call > 0:
                    self.__record_instruction(f'LDWA 0,s')


    ####
    ## Handling While loops (only variable OP variable)
    ####

    def visit_While(self, node):
        loop_id = self.__identify()
        inverted = {
            ast.Lt:  'BRGE', # '<'  in the code means we branch if '>=' 
            ast.LtE: 'BRGT', # '<=' in the code means we branch if '>' 
            ast.Gt:  'BRLE', # '>'  in the code means we branch if '<='
            ast.GtE: 'BRLT', # '>=' in the code means we branch if '<'
            ast.Eq: 'BRNE', # '==' in the code means we branch if '!='
            ast.NotEq: 'BREQ', # '!=' in the code means we branch if '=='
        }
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
    ## Handling function defenitions
    ####
    def visit_FunctionDef(self, node):
        self.__record_instruction(f'; *** {node.name} function definition')
        counter = 0
        loc_vars = {}    # local vars symbol table
        params = {} # params/args symbol table

        self.func_def = True

        # creating .EQUATE statments for each local var
        self.__record_instruction(f'; local variables:')
        for i in node.body:
            if isinstance(i, ast.Assign):
                # ensure we only alias each var one time
                if i.targets[0].id not in loc_vars:
                    loc_vars[i.targets[0].id] = "f"+i.targets[0].id
                    self.__record_instruction(f'{str(loc_vars[i.targets[0].id]+":"):<9}\t.EQUATE {counter}\t ; local variable #2d') # aliasing name
                    counter += 2
                    self.temp_loc_vars[i.targets[0].id] = "f"+i.targets[0].id
                    self.actual_loc_vars[i.targets[0].id] = "f"+i.targets[0].id
                    
                    
        
        # the stack stores the call return address between the loc vars and (params, ret vals)
        counter += 2
        self.__record_instruction(f'; The call return address is stored in between')


        # creating .EQUATE statments for each argumet
        for i in (node.args.args):
                params[i.arg] = "m"+i.arg
                self.__record_instruction(f'{str(params[i.arg]+":"):<9}\t.EQUATE {counter}\t ; parameter {i.arg} #2d')
                counter += 2
                self.temp_loc_vars[i.arg] = "m"+i.arg
                self.actual_arguments[i.arg] = "m"+i.arg
                

        
        # check for return value
        for i in (node.body):
            if isinstance(i, ast.Return):
                self.__record_instruction(f'{str(node.name[0:1]+"ret"+":"):<9}\t.EQUATE {counter}\t ; return value #2d')
                self.ret_name = node.name
                
                
        
        # if at least 1 local variable
        if loc_vars:
            st = ""
            for i in loc_vars.values():
                st = st + ("#"+i+" ")
            self.__record_instruction(f'{str(node.name+":"):<9}\tSUBSP {len(loc_vars)*2},i \t ; push {st}') 
        else:
            self.__record_instruction(f'{str(node.name+":"):<9}\tNOP1') 
        for i in node.body:
            self.visit(i)


        self.func_def = False
        self.pre_finalize()


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
        if len(node.id) > 8:
            name = self.name_mapping[node.id]
        else:
            name = node.id   

        
        # accessing local var, load from stack
        if node.id  in self.temp_loc_vars:
            self.__record_instruction(f'{instruction} {self.temp_loc_vars[name]},s', label)
        # accessing a private variable
        elif self.isPrivate(node.id):
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


        
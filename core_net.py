import sympy as sp
import numpy as np
from scipy.constants import e,pi,h,hbar
from sympy.core.mul import Mul,Pow,Add
from copy import deepcopy
from json import load
import matplotlib.pyplot as plt
from numbers import Number
from math import floor
from time import sleep
phi_0 = hbar/2./e
id2 = sp.Matrix([[1,0],[0,1]])
exponent_to_letter = {
    -18:'a',
    -15:'f',
    -12:'p',
    -9:'n',
    -6:'u',
    -3:'m',
    0:'',
    3:'k',
    6:'M',
    9:'G',
    12:'T'
}
exponent_to_letter_math = {
    -18:'a',
    -15:'f',
    -12:'p',
    -9:'n',
    -6:r'$\mu$',
    -3:'m',
    0:'',
    3:'k',
    6:'M',
    9:'G',
    12:'T'
}
exponent_to_letter_unicode = {
    -18:'a',
    -15:'f',
    -12:'p',
    -9:'n',
    -6:u'\u03bc',
    -3:'m',
    0:'',
    3:'k',
    6:'M',
    9:'G',
    12:'T'
}

pp={
    "element_width":1.2,
    "element_height":0.6,
    "margin":0.1,
    "element_height_normal_modes":1.0,
    "figsize_scaling":1.,
    "color":[0.15,0.15,0.15],
    "x_fig_margin":0.2,
    "y_fig_margin":0.3,
    "C":{
        "gap":0.2,
        "height":0.27,
        "lw":6
    },
    "J":{
        "width":0.2,
        "lw":6
    },
    "L":{
        "width":0.7,
        "height":0.3,
        "N_points":150,
        "N_turns":5,
        "lw":2
    },
    "R":{
        "width":0.6,
        "height":0.35,
        "N_points":150,
        "N_ridges":4,
        "lw":2
    },
    "P":{
        "side_wire_width":0.25
    },
    "W":{
        "lw":1
    },
    "label":{
        "fontsize":10,
        "text_position":[0.0,-0.35]
    },
    "normal_mode_label":{
        "fontsize":10,
        "y_arrow":0.26,
        "y_text":0.37
    },
    "normal_mode_arrow":{
        "logscale":"False",
        "min_width":0.1,
        "max_width":0.5,
        "min_lw":1,
        "max_lw":3,
        "min_head":0.07,
        "max_head":0.071,
        "color_positive":[0.483, 0.622, 0.974],
        "color_negative":[0.931, 0.519, 0.406]
    }
}


class Qcircuit(object):
    """docstring for BBQcircuit"""
    def __init__(self, elements):
        super(Qcircuit, self).__init__()
        self.elements = elements
        self.network = Network(elements)

        self.inductors = []
        self.capacitors = []
        self.junctions = []
        self.resistors = []
        self.no_value_components = []
        for elt in elements:
            elt.head = self
            elt.set_component_lists()

        if len(self.junctions)>1:
            self.ref_elt = self.junctions[0]
        else:
            self.ref_elt = self.inductors[0]

        self.Q_min = 1.
        self.Y = self.network.admittance(self.ref_elt.node_minus,self.ref_elt.node_plus)         
        Y_together = sp.together(self.Y)
        Y_numer = sp.numer(Y_together)       # Extract the numerator of Y(w)
        Y_denom = sp.denom(Y_together)       # Extract the numerator of Y(w)
        Y_numer_poly = sp.collect(sp.expand(Y_numer),sp.Symbol('w')) # Write numerator as polynomial in omega
        Y_denom_poly = sp.collect(sp.expand(Y_denom),sp.Symbol('w')) # Write numerator as polynomial in omega
        self.Y_numer_poly_order = sp.polys.polytools.degree(Y_numer_poly,gen = sp.Symbol('w')) # Order of the polynomial
        self.Y_denom_poly_order = sp.polys.polytools.degree(Y_denom_poly,gen = sp.Symbol('w')) # Order of the polynomial

        self.Y_numer_poly_coeffs_analytical = [Y_numer_poly.coeff(sp.Symbol('w'),n) for n in range(self.Y_numer_poly_order+1)[::-1]] # Get polynomial coefficients
        self.Y_numer_poly_coeffs_analytical = [sp.utilities.lambdify(self.no_value_components,c,'numpy') for c in self.Y_numer_poly_coeffs_analytical]

        self.Y_denom_poly_coeffs_analytical = [Y_denom_poly.coeff(sp.Symbol('w'),n) for n in range(self.Y_denom_poly_order+1)[::-1]] # Get polynomial coefficients
        self.Y_denom_poly_coeffs_analytical = [sp.utilities.lambdify(self.no_value_components,c,'numpy') for c in self.Y_denom_poly_coeffs_analytical]

        self.flux_transformation_dict = {}
        for node in self.network.nodes:
            self.flux_transformation_dict[node] = {}


    def dY(self,w,**kwargs):
        # derivative of u/v is (du*v-dv*u)/v^2
        u = sum([np.array([complex(a*_w**(self.Y_numer_poly_order-n)) for _w in w]) for n,a in enumerate(self.Y_numer_poly_coeffs(**kwargs))])
        v = sum([np.array([complex(a*_w**(self.Y_denom_poly_order-n)) for _w in w]) for n,a in enumerate(self.Y_denom_poly_coeffs(**kwargs))])
        du = sum([np.array([complex((self.Y_numer_poly_order-n)*a*_w**(self.Y_numer_poly_order-n-1)) for _w in w]) for n,a in enumerate(self.Y_numer_poly_coeffs(**kwargs))])
        dv = sum([np.array([complex((self.Y_denom_poly_order-n)*a*_w**(self.Y_denom_poly_order-n-1)) for _w in w]) for n,a in enumerate(self.Y_denom_poly_coeffs(**kwargs))])

        return (du*v-dv*u)/v**2

    def Y_numer_poly_coeffs(self,**kwargs):
        return [complex(coeff(**kwargs)) for coeff in self.Y_numer_poly_coeffs_analytical]
    def Y_denom_poly_coeffs(self,**kwargs):
        return [complex(coeff(**kwargs)) for coeff in self.Y_denom_poly_coeffs_analytical]

    def w_k_A_chi(self,pretty_print = False,**kwargs):
        
        list_element = None
        list_values = None
        for el,value in kwargs.items():
            try:
                iter(value)
            except TypeError:
                iterable = False
            else:
                iterable = True

            if iterable and list_element is None:
                list_element = el 
                list_values = value
            elif iterable and list_element is not None:
                raise ValueError("You can only iterate over the value of one element.")

        if pretty_print == True and list_element is not None:
            raise ValueError("Cannot pretty print since $%s$ does not have a unique value"%list_element)

        if list_element is None:

            to_return =  self.eigenfrequencies(**kwargs),\
                    self.loss_rates(**kwargs),\
                    self.anharmonicities(**kwargs),\
                    self.kerr(**kwargs)

            if pretty_print:
                N_modes = len(to_return[0])
                table_line = ""
                for i in range(4):
                    table_line += " %7s |"
                table_line += "\n"

                to_print = table_line%("mode"," freq. "," diss. "," anha. ")
                for i,w in enumerate(to_return[0]):
                    to_print+=table_line%tuple([str(i)]+[pretty_value(to_return[j][i],use_math = False)+'Hz' for j in range(3)])

                to_print += "\nKerr coefficients\n(diagonal = Kerr, off-diagonal = cross-Kerr)\n"


                table_line = ""
                for i in range(N_modes+1):
                    table_line += " %7s |"
                table_line += "\n"

                to_print += table_line%tuple(['mode']+[str(i)+'   ' for i in range(N_modes)])

                for i in range(N_modes):
                    line_elements = [str(i)]
                    for j in range(N_modes):
                        if i>=j:
                            line_elements.append(pretty_value(to_return[3][i][j],use_math = False)+'Hz')
                        else:
                            line_elements.append("")
                    to_print += table_line%tuple(line_elements)
                print(to_print)

            return to_return

        else:
            w = []
            k = []
            A = []
            kerr = []
            for value in list_values:
                kwargs_single = deepcopy(kwargs)
                kwargs_single[list_element] = value
                w.append(self.eigenfrequencies(**kwargs_single))
                k.append(self.loss_rates(**kwargs_single))
                A.append(self.anharmonicities(**kwargs_single))
                kerr.append(self.kerr(**kwargs_single))
            w = np.moveaxis(np.array(w),0,-1)
            k = np.moveaxis(np.array(k),0,-1)
            A = np.moveaxis(np.array(A),0,-1)
            kerr = np.moveaxis(np.array(kerr),0,-1)
            return w,k,A,kerr

    def check_kwargs(self,**kwargs):
        for key in kwargs:
            if key in self.no_value_components:
                pass
            elif key in [c.label for _,c in self.component_dict.iteritems()]:
                raise ValueError('The value of %s was already specified when constructing the circuit'%key)
            else:
                raise ValueError('%s is not the label of a circuit element'%key)

        for label in self.no_value_components:
            try:
                kwargs[label]
            except Exception as e:
                raise ValueError('The value of %s should be specified with the keyword argument %s=... '%(label,label))

    def set_w_cpx(self,**kwargs):
        self.check_kwargs(**kwargs)
        ws_cpx = np.roots(self.Y_numer_poly_coeffs(**kwargs))

        # take only roots with a positive real part (i.e. freq) 
        # and significant Q factors
        relevant_sols = np.argwhere((np.real(ws_cpx)>=0.)&(np.imag(ws_cpx)>=0.)&(np.real(ws_cpx)>self.Q_min*np.imag(ws_cpx)))
        ws_cpx=ws_cpx[relevant_sols][:,0]
    
        # Sort solutions with increasing frequency
        order = np.argsort(np.real(ws_cpx))
        self.w_cpx = ws_cpx[order]

    def eigenfrequencies(self,**kwargs):
        self.set_w_cpx(**kwargs)
        return np.real(self.w_cpx)/2./pi

    def loss_rates(self,**kwargs):
        self.set_w_cpx(**kwargs)
        return np.imag(self.w_cpx)/2./pi
    
    def anharmonicities_per_junction(self,pretty_print =False,**kwargs):
        self.set_w_cpx(**kwargs)

        if len(self.junctions) == 0:
            raise UserWarning("There are no junctions and hence no anharmonicity in the circuit")
            return []

        elif len(self.junctions) == 1:
            def flux_wr_ref(w,**kwargs):
                return 1.
            self.junctions[0].flux_wr_ref = flux_wr_ref
            return [self.junctions[0].anharmonicity(self.w_cpx,**kwargs)/h]

        else:
            for j in self.junctions:
                j.set_flux_wr_ref()
            return [j.anharmonicity(self.w_cpx,**kwargs)/h for j in self.junctions]

    def kerr(self,**kwargs):
        As =  self.anharmonicities_per_junction(**kwargs)
        N_modes = len(As[0])
        N_junctions = len(As)

        Ks = np.zeros((N_modes,N_modes))
        for i in range(N_modes):
            line = []
            for j in range(N_modes):
                for k in range(N_junctions):
                    if i==j:
                        Ks[i,j]+=np.absolute(As[k][i])
                    else:
                        Ks[i,j]+=2.*np.sqrt(np.absolute(As[k][i])*np.absolute(As[k][j]))
        return Ks

    def anharmonicities(self,**kwargs):
        Ks = self.kerr(**kwargs)
        return [Ks[i,i] for i in range(Ks.shape[0])]



class Network(object):
    """docstring for Network"""
    def __init__(self, netlist):

        # construct node_names
        self.nodes = []
        for elt in netlist:
            nodes = [elt.node_minus,elt.node_plus]
            for node in nodes:
                if node not in self.nodes:
                    self.nodes.append(node)

        # initialize netlist_dict
        self.net_dict = {}
        for node in self.nodes:
            self.net_dict[node] = {}
        for elt in netlist:
            self.connect(elt,elt.node_minus,elt.node_plus)

    def connect(self,element,node_minus,node_plus):
        try:
            self.net_dict[node_minus][node_plus] = self.net_dict[node_minus][node_plus]|element
        except KeyError:
            self.net_dict[node_minus][node_plus] = element

        try:
            self.net_dict[node_plus][node_minus] = self.net_dict[node_plus][node_minus]|element
        except KeyError:
            self.net_dict[node_plus][node_minus] = element

    def remove_node(self,node):

        connections = [x for x in self.net_dict[node].items()]

        # Sum of admittances
        sum_Y = sum([elt.admittance() for _,elt in connections])

        # Prepare mesh
        mesh_to_add = []
        for i,(node_A,elt_A) in enumerate(connections):
            for node_B,elt_B in connections[i+1:]:
                Y = elt_A.admittance()*elt_B.admittance()/sum_Y
                mesh_to_add.append([Admittance(Y),node_A,node_B])
        # Remove star
        for other_node in self.net_dict[node]:
            del self.net_dict[other_node][node]
        del self.net_dict[node]

        # Add mesh
        for mesh_branch in mesh_to_add:
            self.connect(mesh_branch[0],mesh_branch[1],mesh_branch[2])

    def admittance(self,node_minus,node_plus):
        network_to_reduce = deepcopy(self)
        for node in self.nodes:
            if node not in [node_minus,node_plus]:
                network_to_reduce.remove_node(node)

        Y = network_to_reduce.net_dict[node_minus][node_plus].admittance()
        return Y

    def branch_impedance(self,node_1, node_2):
        try:
            return 1./self.net_dict[node_1][node_2].admittance()
        except KeyError:
            return 0.

    def transfer(self,node_left_minus,node_left_plus,node_right_minus,node_right_plus):


        if (node_left_minus in [node_right_plus,node_right_minus]) and (node_left_plus in [node_right_plus,node_right_minus]):
            return 1.

        # Reduce network
        network_to_reduce = deepcopy(self)
        for node in self.nodes:
            if node not in [node_left_minus,node_left_plus,node_right_minus,node_right_plus]:
                network_to_reduce.remove_node(node)


        if (node_left_minus in [node_right_plus,node_right_minus]) or (node_left_plus in [node_right_plus,node_right_minus]):
            if node_left_minus == node_right_minus:
                Z = network_to_reduce.branch_impedance(node_left_minus,node_right_minus)
            elif node_left_plus == node_right_plus:
                Z = network_to_reduce.branch_impedance(node_left_plus,node_right_plus)

            elif node_left_minus == node_right_plus:
                Z = -network_to_reduce.branch_impedance(node_left_minus,node_right_plus)
            elif node_left_plus == node_right_minus:
                Z = -network_to_reduce.branch_impedance(node_left_plus,node_right_minus)

            # see Pozar
            ABCD = sp.Matrix([[1,Z],[0,1]])


        else:
            # Compute ABCD of lattice network
            # see https://www.globalspec.com/reference/71734/203279/10-11-lattice-networks
            # Network Analysis & Circuit (By M. Arshad )section 10.11: LATTICE NETWORKS
            Za = network_to_reduce.branch_impedance(node_left_plus,node_right_plus)
            Zb = network_to_reduce.branch_impedance(node_left_minus,node_right_plus)
            Zc = network_to_reduce.branch_impedance(node_left_plus,node_right_minus)
            Zd = network_to_reduce.branch_impedance(node_left_minus,node_right_minus)
            sum_Z = sum([Za,Zb,Zc,Zd])
            Z11 = (Za+Zb)*(Zd+Zc)/sum_Z
            Z21 = (Zb*Zc-Za*Zd)/sum_Z
            Z22 = (Za+Zc)*(Zd+Zb)/sum_Z

            # see Pozar
            ABCD = sp.Matrix([[
                Z11/Z21,
                Z11*Z22/Z21-Z21],[
                1/Z21,
                Z22/Z21
                ]])

        # Connect missing two elements
        Y_L = network_to_reduce.branch_impedance(node_left_plus,node_left_minus)
        Y_R = network_to_reduce.branch_impedance(node_right_plus,node_right_minus)
        ABCD_L = sp.Matrix([[1,0],[Y_L,1]])
        ABCD_R = sp.Matrix([[1,0],[Y_R,1]])
        ABCD = ABCD_L*ABCD*ABCD_R

        tr = 1/ABCD[0,0]
        return tr



class Circuit(object):
    """docstring for Circuit"""
    def __init__(self,node_minus,node_plus):
        self.node_minus = node_minus
        self.node_plus = node_plus
        self.head = None 

    def __or__(self, other_circuit):
        return Parallel(self, other_circuit)

    def show(self,
        plot = True,
        full_output = False,
        add_vertical_space = False,
        save_to = None,
        **savefig_kwargs):

        if add_vertical_space:
            pp['elt_height'] = pp['element_height_normal_modes']
        else:
            pp['elt_height'] = pp['element_height']

        element_x,element_y,w,h,xs,ys,element_names,line_type = self.draw(pos = [0.,0.], which = 't',is_first_element_to_plot = True)
        x_min = min([np.amin(x) for x in xs])
        x_max = max([np.amax(x) for x in xs])
        y_min = min([np.amin(x) for x in ys])
        y_max = max([np.amax(x) for x in ys])

        x_margin = pp['x_fig_margin']
        y_margin = pp['y_fig_margin'] # ensures that any text labels are not cutoff
        fig = plt.figure(figsize = ((w+2.*x_margin)*pp["figsize_scaling"],(h+2.*y_margin)*pp["figsize_scaling"]))
        ax = fig.add_subplot(111)
        plt.subplots_adjust(left=0., right=1., top=1., bottom=0.)

        for i in range(len(xs)):
            ax.plot(xs[i],ys[i],color = pp["color"],lw=pp[line_type[i]]['lw'])

        element_positions = {}
        for i,el in enumerate(element_names):
            plt.text(
                element_x[i]+pp['label']['text_position'][0],
                element_y[i]+pp['label']['text_position'][1],
                el.to_string(),
                fontsize=pp['label']['fontsize']
                ,ha='center')
            element_positions[el] = [element_x[i],element_y[i]]

        ax.set_axis_off()
        ax.set_xlim(x_min-x_margin,x_max+x_margin)
        ax.set_ylim(y_min-y_margin,y_max+y_margin)
        plt.margins(x=0.,y=0.)

        if full_output:
            return element_positions,fig,ax

        if save_to is not None:
            fig.savefig(save_to,transparent = True,**savefig_kwargs)
        if plot:
            plt.show()
        plt.close()

class Parallel(Circuit):
    """docstring for Connection"""
    def __init__(self, left, right):
        super(Parallel, self).__init__(node_minus = None,node_plus = None)

        # sets the two children circuit elements
        self.left = left
        self.right = right
   
    def admittance(self):
        return Add(
            self.left.admittance(),
            self.right.admittance())

        

class Component(Circuit):
    """docstring for Component"""
    def __init__(self, node_minus, node_plus, arg1 = None, arg2 = None):
        super(Component, self).__init__(node_minus, node_plus)
        self.label = None
        self.value = None
        self.flux_wr_ref = None

        if arg1 is None and arg2 is None:
            raise ValueError("Specify either a value or a label")
        for a in [arg1,arg2]:
            if a is None:
                pass
            elif type(a) is str:
                self.label = a
            else:
                self.value = float(a)

    def __hash__(self):
        if self.label is None:
            return hash(str(self.value)+self.unit)
        else:
            if self.value is None:
                return hash(self.label+self.unit)
            else:
                return hash(str(self.value)+self.label+self.unit)

    def get_value(self,**kwargs):
        if self.value is not None:
            return self.value
        elif self.value is None and kwargs is not None:
            if self.label in [k for k in kwargs]:
                return kwargs[self.label]
        
        return sp.Symbol(self.label)

    def set_component_lists(self):
        if self.value is None:
            if self.label in self.head.no_value_components:
                raise ValueError("Two components may not have the same name %s"%self.label)
            else:
                self.head.no_value_components.append(self.label)

    def set_flux_wr_ref(self):
        if self.flux_wr_ref is None:
            try:
                tr = self.head.flux_transformation_dict[self.node_minus,self.node_plus]
            except KeyError:
                tr = self.head.network.transfer(self.head.ref_elt.node_minus,self.head.ref_elt.node_plus,self.node_minus,self.node_plus)
                self.head.flux_transformation_dict[self.node_minus,self.node_plus] = tr
                self.head.flux_transformation_dict[self.node_plus,self.node_minus] = -tr
            
            self.flux_wr_ref = sp.utilities.lambdify(['w']+self.head.no_value_components,tr,"numpy")


    def flux(self,w,**kwargs):
        ImdY = np.imag(self.head.dY(w,**kwargs))
        return complex(self.flux_wr_ref(w,**kwargs)*sp.sqrt(hbar/w/ImdY))

    def voltage(self,w,**kwargs):
        return complex(self.flux(w,**kwargs)*1j*w)

    def current(self,w,**kwargs):
        kwargs['w']=w
        Y = self.admittance()
        if isinstance(Y, Number):
            pass
        else:
            Y = Y.evalf(subs=kwargs)
        return complex(self.voltage(**kwargs)*Y)

    def charge(self,w,**kwargs):
        return self.current(w,**kwargs)/w

    def to_string(self,use_math = True,use_unicode = False):

        unit = self.unit
        if use_unicode:
            unit = unit.replace(r'$\Omega$',u"\u03A9")
        if use_math == False:
            unit = unit.replace(r'$\Omega$','Ohm')

        label = self.label
        if use_math:
            label = "$%s$"%(label)

        if self.value is not None:
            pvalue = pretty_value(self.value,use_math = use_math,use_unicode = use_unicode)

        if self.label is None:
            return pvalue+unit
        elif self.label == '' and self.value is None:
            return ''
        elif self.value is None:
            return label
        elif self.label == '' and self.value is not None:
            return pvalue+unit
        else:
            return label+'='+pvalue+unit


class W(Component):
    """docstring for Wire"""
    def __init__(self, node_minus,node_plus,arg1 = '',arg2 = None):
        super(W,self).__init__(node_minus, node_plus,arg1,arg2)
        self.type = 'W'

    def to_string(*args,**kwargs):
        return 'W'

class L(Component):
    def __init__(self,node_minus, node_plus, arg1 = None, arg2 = None):
        super(L,self).__init__(node_minus, node_plus,arg1,arg2)
        self.unit = 'H'
        self.type = 'L'
    def admittance(self):
        return -sp.I*Mul(1/sp.Symbol('w'),1/self.get_value())

    def set_component_lists(self):
        super(L, self).set_component_lists()
        self.head.inductors.append(self)
    def draw(self,pos,which,is_first_element_to_plot = False):

        x = np.linspace(0.5,float(pp['L']['N_turns']) +1. ,pp['L']['N_points'])
        y = -np.sin(2.*np.pi*x)
        x = np.cos(2.*np.pi*x)+2.*x

        line_type = []
        line_type.append('L')
            
        # reset leftmost point to 0
        x_min = x[0]
        x -= x_min

        # set width inductor width
        x_max = x[-1]
        x *= pp['L']['width']/x_max

        # set leftmost point to the length of 
        # the side connection wires
        x +=(pp['element_width']-pp['L']['width'])/2.   

        # add side wire connections
        x_min = x[0]
        x_max = x[-1]
        x_list = [x]
        x_list += [np.array([0.,x_min])]
        x_list += [np.array([x_max,pp['element_width']])]
        line_type.append('W')
        line_type.append('W')

        # Shift into position in x 
        for i,x in enumerate(x_list):
            if which == 'l':
                x_list[i]+=pos[0]
            elif which == 't':
                x_list[i]+=pos[0]-pp['element_width']/2.


        # set height of inductor
        y *=pp['L']['height']/2.

        # add side wire connections
        y_list = [y]
        y_list += [np.array([0.,0.])]
        y_list += [np.array([0.,0.])]

        for i,y in enumerate(y_list):
            if which == 'l':
                y_list[i]+=pos[1]
            elif which == 't':
                y_list[i]+=pos[1]-pp['elt_height']/2.

        if which == 'l':
            pos_x = pos[0]+pp['element_width']/2.
            pos_y = pos[1]
            height = pp['L']['height']
        elif which == 't':
            pos_x = pos[0]
            pos_y = pos[1]-pp['elt_height']/2.
            height = pp['elt_height']

        return [pos_x],[pos_y],pp['element_width'],height,x_list,y_list,[self],line_type

class J(L):
    def __init__(self, node_minus, node_plus,arg1 = None, arg2 = None,use_E=False,use_I=False):
        super(J,self).__init__(node_minus, node_plus,arg1,arg2)
        self.type = 'J'

        self.use_E = use_E
        self.use_I = use_I
        if self.use_E:
            self.unit = 'Hz'
        elif self.use_I:
            self.unit = 'A'
        else:
            self.unit = 'H'

    def get_value(self,**kwargs):
        value = super(J,self).get_value(**kwargs)
        if (self.use_E == False) and (self.use_I ==False):
            return value
        elif (self.use_E == True) and (self.use_I ==False):
            L = (hbar/2./e)**2/(value*h) # E is assumed to be provided in Hz
            return L
        elif (use_E == False) and (use_I ==True):
            L = (hbar/2./e)/value
            return L
        else:
            raise ValueError("Cannot set both use_E and use_I to True")

    def set_component_lists(self):
        super(J, self).set_component_lists()
        self.head.junctions.append(self)

    def anharmonicity(self,w,**kwargs):
        ImdY = np.imag(self.head.dY(w,**kwargs))
        return self.flux_wr_ref(w,**kwargs)**4*2.*e**2/self.get_value(**kwargs)/w**2/ImdY**2
    def draw(self,pos,which,is_first_element_to_plot = False):
        
        line_type = []
        x = [
            np.array([0.,pp['element_width']]),
            np.array([(pp['element_width']-pp['J']['width'])/2.,(pp['element_width']+pp['J']['width'])/2.]),
            np.array([(pp['element_width']-pp['J']['width'])/2.,(pp['element_width']+pp['J']['width'])/2.])
        ]
        y = [
            np.array([0.,0.]),
            np.array([-1.,1.])*pp['J']['width']/2.,
            np.array([1.,-1.])*pp['J']['width']/2.
        ]
        line_type.append('W')
        line_type.append('J')
        line_type.append('J')
        
        for i,_ in enumerate(x):
            if which == 'l':
                x[i]+=pos[0]
                y[i]+=pos[1]
                pos_x = pos[0]+pp['element_width']/2.
                pos_y = pos[1]
                height = pp['J']['width']
            elif which == 't':
                x[i]+=pos[0]-pp['element_width']/2.
                y[i]+=pos[1]-pp['elt_height']/2.
                pos_x = pos[0]
                pos_y = pos[1]-pp['elt_height']/2.
                height = pp['elt_height']

        return [pos_x],[pos_y],pp['element_width'],height,x,y,[self],line_type

class R(Component):
    def __init__(self,node_minus, node_plus, arg1 = None, arg2 = None):
        super(R, self).__init__(node_minus, node_plus,arg1,arg2)
        self.unit = r'$\Omega$'
        self.type = R

    def admittance(self):
        return 1/self.get_value()

    def set_component_lists(self):
        super(R, self).set_component_lists()
        self.head.resistors.append(self)
    def draw(self,pos,which,is_first_element_to_plot = False):

        x = np.linspace(-0.25,0.25+float(pp['R']['N_ridges']),pp['R']['N_points'])
        height = 1.
        period = 1.
        a = height*2.*(-1.+2.*np.mod(np.floor(2.*x/period),2.))
        b = -height*2.*np.mod(np.floor(2.*x/period),2.)
        y = (2.*x/period - np.floor(2.*x/period))*a+b+height

        line_type = []
        line_type.append('R')
            
        # reset leftmost point to 0
        x_min = x[0]
        x -= x_min

        # set width inductor width
        x_max = x[-1]
        x *= pp['R']['width']/x_max

        # set leftmost point to the length of 
        # the side connection wires
        x +=(pp['element_width']-pp['R']['width'])/2.   

        # add side wire connections
        x_min = x[0]
        x_max = x[-1]
        x_list = [x]
        x_list += [np.array([0.,x_min])]
        x_list += [np.array([x_max,pp['element_width']])]
        line_type.append('W')
        line_type.append('W')

        # Shift into position in x 
        for i,x in enumerate(x_list):
            if which == 'l':
                x_list[i]+=pos[0]
            elif which == 't':
                x_list[i]+=pos[0]-pp['element_width']/2.


        # set height of inductor
        y *=pp['R']['height']/2.

        # add side wire connections
        y_list = [y]
        y_list += [np.array([0.,0.])]
        y_list += [np.array([0.,0.])]

        for i,y in enumerate(y_list):
            if which == 'l':
                y_list[i]+=pos[1]
            elif which == 't':
                y_list[i]+=pos[1]-pp['elt_height']/2.

        if which == 'l':
            pos_x = pos[0]+pp['element_width']/2.
            pos_y = pos[1]
            height = pp['R']['height']
        elif which == 't':
            pos_x = pos[0]
            pos_y = pos[1]-pp['elt_height']/2.
            height = pp['elt_height']

        return [pos_x],[pos_y],pp['element_width'],height,x_list,y_list,[self],line_type        

class C(Component):
    def __init__(self, node_minus, node_plus,arg1 = None, arg2 = None):
        super(C, self).__init__(node_minus, node_plus,arg1,arg2)
        self.unit = 'F'
        self.type = 'C'
    def admittance(self):
        return sp.I*Mul(sp.Symbol('w'),self.get_value())

    def set_component_lists(self):
        super(C, self).set_component_lists()
        self.head.capacitors.append(self)
    def draw(self,pos,which,is_first_element_to_plot = False):
        line_type = []
        x = [
            np.array([0.,(pp['element_width']-pp['C']['gap'])/2.]),
            np.array([(pp['element_width']+pp['C']['gap'])/2.,pp['element_width']]),
            np.array([(pp['element_width']-pp['C']['gap'])/2.,(pp['element_width']-pp['C']['gap'])/2.]),
            np.array([(pp['element_width']+pp['C']['gap'])/2.,(pp['element_width']+pp['C']['gap'])/2.]),
        ]
        y = [
            np.array([0.,0.]),
            np.array([0.,0.]),
            np.array([-pp['C']['height']/2.,pp['C']['height']/2.]),
            np.array([-pp['C']['height']/2.,pp['C']['height']/2.]),
        ]
        line_type.append('W')
        line_type.append('W')
        line_type.append('C')
        line_type.append('C')
        
        for i,_ in enumerate(x):
            if which == 'l':
                x[i]+=pos[0]
                y[i]+=pos[1]
                pos_x = pos[0]+pp['element_width']/2.
                pos_y = pos[1]
                height = pp['C']['height']
            elif which == 't':
                x[i]+=pos[0]-pp['element_width']/2.
                y[i]+=pos[1]-pp['elt_height']/2.
                pos_x = pos[0]
                pos_y = pos[1]-pp['elt_height']/2.
                height = pp['elt_height']

        return [pos_x],[pos_y],pp['element_width'],height,x,y,[self],line_type
class Admittance(Component):
    def __init__(self, Y):
        self.Y = Y

    def admittance(self):
        return self.Y
    def draw(self,pos,which,is_first_element_to_plot = False):
        line_type = []
        x = [
            np.array([0.,(pp['element_width']-pp['C']['gap'])/2.]),
            np.array([(pp['element_width']+pp['C']['gap'])/2.,pp['element_width']]),
            np.array([(pp['element_width']-pp['C']['gap'])/2.,(pp['element_width']-pp['C']['gap'])/2.]),
            np.array([(pp['element_width']+pp['C']['gap'])/2.,(pp['element_width']+pp['C']['gap'])/2.]),
        ]
        y = [
            np.array([0.,0.]),
            np.array([0.,0.]),
            np.array([-pp['C']['height']/2.,pp['C']['height']/2.]),
            np.array([-pp['C']['height']/2.,pp['C']['height']/2.]),
        ]
        line_type.append('W')
        line_type.append('W')
        line_type.append('C')
        line_type.append('C')
        
        for i,_ in enumerate(x):
            if which == 'l':
                x[i]+=pos[0]
                y[i]+=pos[1]
                pos_x = pos[0]+pp['element_width']/2.
                pos_y = pos[1]
                height = pp['C']['height']
            elif which == 't':
                x[i]+=pos[0]-pp['element_width']/2.
                y[i]+=pos[1]-pp['elt_height']/2.
                pos_x = pos[0]
                pos_y = pos[1]-pp['elt_height']/2.
                height = pp['elt_height']

        return [pos_x],[pos_y],pp['element_width'],height,x,y,[self],line_type

def pretty_value(v,use_power_10 = False,use_math = True,use_unicode = False):
    if v == 0:
        return '0'
    exponent = floor(np.log10(v))
    exponent_3 = exponent-(exponent%3)
    float_part = v/(10**exponent_3)
    if use_power_10 or v>=1e15 or v<1e-18:
        if exponent_3 == 0:
            exponent_part = ''
        else:
            if use_math:
                exponent_part = r'$\times 10^{%d}$'%exponent_3
            else:
                exponent_part = r'e%d'%exponent_3
    else:
        if use_unicode:
            exponent_part = ' '+exponent_to_letter_unicode[exponent_3]
        elif use_math:
            exponent_part = ' '+exponent_to_letter_math[exponent_3]
        else:
            exponent_part = ' '+exponent_to_letter[exponent_3]
    if float_part>=10.:
        pretty = "%.0f%s"%(float_part,exponent_part)
    else:
        pretty = "%.1f%s"%(float_part,exponent_part)
    return pretty

def check_there_are_no_iterables_in_kwarg(**kwargs):
    for el,value in kwargs.items():
        try:
            iter(value)
        except TypeError:
            pass
        else:
            raise ValueError("This function accepts no lists or iterables as input.")

if __name__ == '__main__':

    # n = Network([
    #     R(0,1,1.),
    #     R(1,2,1.),
    #     R(0,2,1.),
    #     ])
    # nl = n.net_dict
    # print nl
    # n.remove_node(1)
    # print nl
    # print nl[0][2].admittance()


    cQED_circuit = Qcircuit([
        C(0,1,100e-15),
        J(0,1,10e-9),
        C(1,2,10e-15),
        C(2,0,64e-15),
        L(2,0,22e-9),
        C(2,0,33e-15),
        L(2,3,45e-9),
        C(0,3,63e-15),
        L(2,3,45e-9),
        C(1,3,63e-15),
        C(0,2,34e-15),
        L(4,3,45e-15),
        L(2,4,67e-9),
        ])
    # print cQED_circuit.eigenfrequencies()
    # print cQED_circuit.loss_rates()
    cQED_circuit.w_k_A_chi(pretty_print = True)
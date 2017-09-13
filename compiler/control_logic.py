from math import log
import design
from tech import drc, parameter
import debug
from contact import contact
from pinv import pinv
from nand_2 import nand_2
from nand_3 import nand_3
from nor_2 import nor_2
import math
from vector import vector
from globals import OPTS

class control_logic(design.design):
    """
    Dynamically generated Control logic for the total SRAM circuit.
    """

    def __init__(self, num_rows):
        """ Constructor """
        design.design.__init__(self, "control_logic")
        debug.info(1, "Creating {}".format(self.name))

        self.num_rows = num_rows
        self.create_layout()
        self.DRC_LVS()

    def create_layout(self):
        """ Create layout and route between modules """
        self.create_modules()
        self.setup_layout_offsets()
        self.add_modules()
        self.add_routing()

    def create_modules(self):
        """ add all the required modules """
        input_lst =["csb","web","oeb","clk"]
        output_lst = ["s_en", "w_en", "tri_en", "tri_en_bar", "clk_bar", "clk_buf"]
        rails = ["vdd", "gnd"]
        for pin in input_lst + output_lst + rails:
            self.add_pin(pin)

        self.nand2 = nand_2()
        self.add_mod(self.nand2)
        self.nand3 = nand_3()
        self.add_mod(self.nand3)
        self.nor2 = nor_2()
        self.add_mod(self.nor2)


        # Special gates: inverters for buffering
        self.inv = self.inv1 = pinv()
        self.add_mod(self.inv1)
        self.inv2 = pinv(nmos_width=2*drc["minwidth_tx"])
        self.add_mod(self.inv2)
        self.inv4 = pinv(nmos_width=4*drc["minwidth_tx"])
        self.add_mod(self.inv4)
        self.inv8 = pinv(nmos_width=8*drc["minwidth_tx"])
        self.add_mod(self.inv8)
        self.inv16 = pinv(nmos_width=16*drc["minwidth_tx"])
        self.add_mod(self.inv16)

        c = reload(__import__(OPTS.config.ms_flop_array))
        ms_flop_array = getattr(c, OPTS.config.ms_flop_array)
        self.msf_control = ms_flop_array(name="msf_control",
                                         columns=3,
                                         word_size=3)
        self.add_mod(self.msf_control)

        c = reload(__import__(OPTS.config.replica_bitline))
        replica_bitline = getattr(c, OPTS.config.replica_bitline)
        self.replica_bitline = replica_bitline(rows=int(math.ceil(self.num_rows / 10.0)))
        self.add_mod(self.replica_bitline)


    def setup_layout_offsets(self):
        """ Setup layout offsets, determine the size of the busses etc """
        # These aren't for instantiating, but we use them to get the dimensions
        self.poly_contact = contact(layer_stack=("poly", "contact", "metal1"))
        self.poly_contact_offset = vector(0.5*self.poly_contact.width,0.5*self.poly_contact.height)
        self.m1m2_via = contact(layer_stack=("metal1", "via1", "metal2"))
        self.m2m3_via = contact(layer_stack=("metal2", "via2", "metal3"))

        # M1/M2 routing pitch is based on contacted pitch
        self.m1_pitch = max(self.m1m2_via.width,self.m1m2_via.height) + max(drc["metal1_to_metal1"],drc["metal2_to_metal2"])
        self.m2_pitch = max(self.m2m3_via.width,self.m2m3_via.height) + max(drc["metal2_to_metal2"],drc["metal3_to_metal3"])

        # Have the cell gap leave enough room to route an M1 wire.
        # Some cells may have pwell/nwell spacing problems too when the wells are different heights.
        self.cell_gap = max(self.m1_pitch,drc["pwell_to_nwell"])
        
        # This corrects the offset pitch difference between M2 and M1
        self.offset_fix = vector(0.5*(drc["minwidth_metal2"]-drc["minwidth_metal1"]),0)

        # Amount to shift a via from center-line path routing to it's offset
        self.m1m2_via_offset = vector(self.m1m2_via.height,-0.5*drc["minwidth_metal2"])
        self.m2m3_via_offset = vector(self.m2m3_via.height,-0.5*drc["minwidth_metal3"])
        
        # First RAIL Parameters: gnd, oe, oebar, cs, we, clk_buf, clk_bar
        self.rail_1_start_x = 0
        self.num_rails_1 = 8
        self.rail_1_names = ["clk_buf", "gnd", "oe_bar", "cs", "we", "vdd",  "oe", "clk_bar"]
        self.overall_rail_1_gap = (self.num_rails_1 + 2) * self.m2_pitch
        self.rail_1_x_offsets = {}

        # Second RAIL Parameters: vdd
        self.rail_2_start_x = 0
        self.num_rails_2 = 0
        self.rail_2_names = ["vdd"]
        self.overall_rail_2_gap = (self.num_rails_2 + 2) * self.m2_pitch
        self.rail_2_x_offsets = {}

        # GAP between main control and replica bitline
        self.replica_bitline_gap = 2*self.m2_pitch



    def add_modules(self):
        """ Place all the modules """
        self.add_control_flops()
        self.add_clk_buffer(0)
        self.add_1st_row(0)
        self.add_2nd_row(self.inv1.height)
        self.add_3rd_row(2*self.inv1.height)

        self.add_control_routing()
        self.add_rbl(0)
        self.add_layout_pins()

        self.height = max(self.replica_bitline.width, 3 * self.inv1.height, self.msf_offset.y)
        self.width = self.replica_bitline_offset.x + self.replica_bitline.height

        


    def add_routing(self):
        """ Routing between modules """
        self.add_clk_routing()
        self.add_trien_routing()
        self.add_rblk_routing()
        self.add_wen_routing()
        self.add_sen_routing()
        self.add_output_routing()
        self.add_supply_routing()

    def add_control_flops(self):
        """ Add the control signal flops for OEb, WEb, CSb. """
        self.msf_offset = vector(0, self.inv.height+self.msf_control.width+2*self.m2_pitch)
        self.msf=self.add_inst(name="msf_control",
                               mod=self.msf_control,
                               offset=self.msf_offset,
                               rotate=270)
        # don't change this order. This pins are meant for internal connection of msf array inside the control logic.
        # These pins are connecting the msf_array inside of control_logic.
        temp = ["oeb", "csb", "web",
                "oe_bar", "oe",
                "cs_bar", "cs",
                "we_bar", "we",
                "clk_buf", "vdd", "gnd"]
        self.connect_inst(temp)

    def add_rbl(self,y_off):
        """ Add the replica bitline """
        
        self.replica_bitline_offset = vector(self.rail_2_end_x , y_off)
        self.rbl=self.add_inst(name="replica_bitline",
                               mod=self.replica_bitline,
                               offset=self.replica_bitline_offset,
                               mirror="MX",
                               rotate=90)
        self.connect_inst(["rblk", "pre_s_en", "vdd", "gnd"])
        
    def add_layout_pins(self):
        """ Add the input/output layout pins. """

        # Top to bottom: CS WE OE signal groups 
        pin_set = ["oeb","csb","web"]
        for (i,pin_name) in zip(range(3),pin_set):
            subpin_name="din[{}]".format(i)
            pin=self.msf.get_pin(subpin_name)
            #pin=self.msf_control.get_pin("din[{}]".format(i))
            self.add_layout_pin(text=pin_name,
                                layer="metal2",
                                offset=pin.ll(),
                                width=pin.width(),
                                height=pin.height())

        pin=self.clk_inv1.get_pin("A")
        self.add_layout_pin(text="clk",
                            layer="metal1",
                            offset=pin.ll(),
                            width=pin.width(),
                            height=pin.height())

        pin=self.clk_inv1.get_pin("gnd")
        self.add_layout_pin(text="gnd",
                            layer="metal1",
                            offset=pin.ll(),
                            width=self.width)

        pin=self.clk_inv1.get_pin("vdd")
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=pin.ll(),
                            width=self.width)
        
    def add_clk_buffer(self,y_off):
        """ Add the multistage clock buffer below the control flops """
        # 4 stage clock buffer
        self.clk_inv1_offset = vector(0, y_off)
        self.clk_inv1=self.add_inst(name="inv_clk1_bar",
                                    mod=self.inv2,
                                    offset=self.clk_inv1_offset)
        self.connect_inst(["clk", "clk1_bar", "vdd", "gnd"])
        self.clk_inv2_offset = self.clk_inv1_offset + vector(self.inv2.width,0)
        self.clk_inv2=self.add_inst(name="inv_clk2",
                                    mod=self.inv4,
                                    offset=self.clk_inv2_offset)
        self.connect_inst(["clk1_bar", "clk2", "vdd", "gnd"])
        self.clk_bar_offset = self.clk_inv2_offset + vector(self.inv4.width,0)
        self.clk_bar=self.add_inst(name="inv_clk_bar",
                                   mod=self.inv8,
                                   offset=self.clk_bar_offset)
        self.connect_inst(["clk2", "clk_bar", "vdd", "gnd"])
        self.clk_buf_offset = self.clk_bar_offset + vector(self.inv8.width,0)
        self.clk_buf=self.add_inst(name="inv_clk_buf",
                                mod=self.inv16,
                                   offset=self.clk_buf_offset)
        self.connect_inst(["clk_bar", "clk_buf", "vdd", "gnd"])
        
        # This is the first rail offset
        self.rail_1_start_x = max(self.msf_offset.x + self.msf_control.height,self.clk_buf_offset.x+self.inv16.width)

    def add_1st_row(self,y_off):

        x_off = self.rail_1_start_x + self.overall_rail_1_gap

        # input: OE, clk_bar,CS output: rblk_bar
        self.rblk_bar_offset = vector(x_off, y_off)
        self.rblk_bar=self.add_inst(name="nand3_rblk_bar",
                                    mod=self.nand3,
                                    offset=self.rblk_bar_offset)
        self.connect_inst(["clk_bar", "oe", "cs", "rblk_bar", "vdd", "gnd"])
        x_off += self.nand3.width

        # input: rblk_bar, output: rblk
        self.rblk_offset = vector(x_off, y_off)
        self.rblk=self.add_inst(name="inv_rblk",
                                mod=self.inv1,
                                offset=self.rblk_offset)
        self.connect_inst(["rblk_bar", "rblk",  "vdd", "gnd"])
        #x_off += self.inv1.width
        
        self.row_1_width = x_off

    def add_2nd_row(self, y_off):
        # start after first rails
        x_off = self.rail_1_start_x + self.overall_rail_1_gap
        y_off += self.inv1.height

        # input: clk_buf, OE_bar output: tri_en
        self.tri_en_offset = vector(x_off, y_off)
        self.tri_en=self.add_inst(name="nor2_tri_en",
                                  mod=self.nor2,
                                  offset=self.tri_en_offset,
                                  mirror="MX")
        self.connect_inst(["clk_buf", "oe_bar", "tri_en", "vdd", "gnd"])
        x_off += self.nor2.width + self.cell_gap
 
        # input: OE, clk_bar output: tri_en_bar
        self.tri_en_bar_offset = vector(x_off,y_off)
        self.tri_en_bar=self.add_inst(name="nand2_tri_en",
                                      mod=self.nand2,
                                      offset=self.tri_en_bar_offset,
                                      mirror="MX")
        self.connect_inst(["oe", "clk_bar",  "tri_en_bar", "vdd", "gnd"])
        x_off += self.nand2.width 

        x_off += self.inv1.width + self.cell_gap
        
        # BUFFER INVERTERS FOR S_EN
        # input: input: pre_s_en_bar, output: s_en
        self.s_en_offset = vector(x_off, y_off)
        self.s_en=self.add_inst(name="inv_s_en",
                                mod=self.inv1,
                                offset=self.s_en_offset,
                                mirror="XY")
        self.connect_inst(["pre_s_en_bar", "s_en",  "vdd", "gnd"])
        x_off += self.inv1.width

        # input: pre_s_en, output: pre_s_en_bar
        self.pre_s_en_bar_offset = vector(x_off, y_off)
        self.pre_s_en_bar=self.add_inst(name="inv_pre_s_en_bar",
                                        mod=self.inv1,
                                        offset=self.pre_s_en_bar_offset,
                                        mirror="XY")
        self.connect_inst(["pre_s_en", "pre_s_en_bar",  "vdd", "gnd"])
        #x_off += self.inv1.width
        
        
        self.row_2_width = x_off
        
    def add_3rd_row(self, y_off):
        # start after first rails
        x_off = self.rail_1_start_x + self.overall_rail_1_gap
        
        # This prevents some M2 outputs from overlapping (hack)
        x_off += self.inv1.width
        
        # input: WE, clk_bar, CS output: w_en_bar
        self.w_en_bar_offset = vector(x_off, y_off)
        self.w_en_bar=self.add_inst(name="nand3_w_en_bar",
                                    mod=self.nand3,
                                    offset=self.w_en_bar_offset)
        self.connect_inst(["clk_bar", "we", "cs", "w_en_bar", "vdd", "gnd"])
        x_off += self.nand3.width

        # input: w_en_bar, output: pre_w_en
        self.pre_w_en_offset = vector(x_off, y_off)
        self.pre_w_en=self.add_inst(name="inv_pre_w_en",
                                    mod=self.inv1,
                                    offset=self.pre_w_en_offset)
        self.connect_inst(["w_en_bar", "pre_w_en",  "vdd", "gnd"])
        x_off += self.inv1.width
        
        # BUFFER INVERTERS FOR W_EN
        self.pre_w_en_bar_offset = vector(x_off, y_off)
        self.pre_w_en_bar=self.add_inst(name="inv_pre_w_en_bar",
                                        mod=self.inv1,
                                        offset=self.pre_w_en_bar_offset)
        self.connect_inst(["pre_w_en", "pre_w_en_bar",  "vdd", "gnd"])
        x_off += self.inv1.width

        self.w_en_offset = vector(x_off,  y_off)
        self.w_en=self.add_inst(name="inv_w_en2",
                                mod=self.inv1,
                                offset=self.w_en_offset)
        self.connect_inst(["pre_w_en_bar", "w_en",  "vdd", "gnd"])
        #x_off += self.inv1.width

        self.row_3_width = x_off

    def add_control_routing(self):
        """ Route the vertical rails for internal control signals  """

        control_rail_height =  max(3 * self.inv1.height, self.msf_offset.y)
        
        for i in range(self.num_rails_1):
            offset = vector(self.rail_1_start_x + (i+1) * self.m2_pitch,0)
            if self.rail_1_names[i] in ["clk_buf", "clk_bar", "vdd", "gnd"]:
                self.add_layout_pin(text=self.rail_1_names[i],
                                    layer="metal2",
                                    offset=offset,
                                    width=drc["minwidth_metal2"],
                                    height=control_rail_height)
            else:
                self.add_rect(layer="metal2",
                              offset=offset,
                              width=drc["minwidth_metal2"],
                              height=control_rail_height)
            self.rail_1_x_offsets[self.rail_1_names[i]]=offset.x + 0.5*drc["minwidth_metal2"] # center offset

        # pins are in order ["oeb","csb","web"] # 0 1 2
        self.connect_rail_from_left_m2m3(self.msf,"dout_bar[0]","oe")
        self.connect_rail_from_left_m2m3(self.msf,"dout[0]","oe_bar")
        self.connect_rail_from_left_m2m3(self.msf,"dout_bar[1]","cs")
        self.connect_rail_from_left_m2m3(self.msf,"dout_bar[2]","we")

        # Connect the gnd and vdd of the control 
        gnd_pins = self.msf.get_pins("gnd")
        for p in gnd_pins:
            if p.layer != "metal2":
                continue
            gnd_pin = p.rc()
            gnd_rail_position = vector(self.rail_1_x_offsets["gnd"], gnd_pin.y)
            self.add_wire(("metal1","via1","metal2"),[gnd_pin, gnd_rail_position, gnd_rail_position - vector(0,self.m2_pitch)])            
            self.add_via(layers=("metal1","via1","metal2"),
                         offset=gnd_pin + self.m1m2_via_offset,
                         rotate=90)

        vdd_pins = self.msf.get_pins("vdd")
        for p in vdd_pins:
            if p.layer != "metal1":
                continue
            clk_vdd_position = vector(p.bc().x,self.clk_buf.get_pin("vdd").uy())
            self.add_path("metal1",[p.bc(),clk_vdd_position])
        
        self.rail_2_start_x = max (self.row_1_width, self.row_2_width, self.row_3_width)
        for i in range(self.num_rails_2):
            offset = vector(self.rail_2_start_x + i * self.m1_pitch, 0)
            self.add_rect(layer="metal1",
                          offset=offset,
                          width=drc["minwidth_metal1"],
                          height=self.logic_height)
            self.rail_2_x_offsets[self.rail_2_names[i]]=offset.x + 0.5*drc["minwidth_metal1"] # center offset
            
        self.rail_2_end_x = self.rail_2_start_x + (self.num_rails_2+1) * self.m2_pitch

    def add_rblk_routing(self):
        """ Connect the logic for the rblk generation """
        self.connect_rail_from_right(self.rblk_bar,"A","clk_bar")
        self.connect_rail_from_right(self.rblk_bar,"B","oe")
        self.connect_rail_from_right(self.rblk_bar,"C","cs")

        # Connect the NAND3 output to the inverter
        # The pins are assumed to extend all the way to the cell edge
        rblk_bar_pin = self.rblk_bar.get_pin("Z").ur()
        inv_in_pin = self.rblk.get_pin("A").ll()
        mid1 = vector(inv_in_pin.x,rblk_bar_pin.y)
        self.add_path("metal1",[rblk_bar_pin,mid1,inv_in_pin])

        # Connect the output to the RBL
        rblk_pin = self.rblk.get_pin("Z").rc()
        rbl_in_pin = self.rbl.get_pin("en").lc()
        mid1 = vector(rblk_pin.x,rbl_in_pin.y)
        self.add_path("metal1",[rblk_pin,mid1,rbl_in_pin])        
                      
    def connect_rail_from_right(self,inst, pin, rail):
        """ Helper routine to connect an unrotated/mirrored oriented instance to the rails """
        in_pin = inst.get_pin(pin).lc()
        rail_position = vector(self.rail_1_x_offsets[rail], in_pin.y)
        self.add_wire(("metal1","via1","metal2"),[in_pin, rail_position, rail_position - vector(0,self.m2_pitch)])

    def connect_rail_from_right_m2m3(self,inst, pin, rail):
        """ Helper routine to connect an unrotated/mirrored oriented instance to the rails """
        in_pin = inst.get_pin(pin).lc()
        rail_position = vector(self.rail_1_x_offsets[rail], in_pin.y)
        self.add_wire(("metal3","via2","metal2"),[in_pin, rail_position, rail_position - vector(0,self.m2_pitch)])
        # Bring it up to M2 for M2/M3 routing
        self.add_via(layers=("metal1","via1","metal2"),
                     offset=in_pin + self.m1m2_via_offset,
                     rotate=90)
        self.add_via(layers=("metal2","via2","metal3"),
                     offset=in_pin + self.m2m3_via_offset,
                     rotate=90)
        
        
    def connect_rail_from_left(self,inst, pin, rail):
        """ Helper routine to connect an unrotated/mirrored oriented instance to the rails """
        in_pin = inst.get_pin(pin).rc()
        rail_position = vector(self.rail_1_x_offsets[rail], in_pin.y)
        self.add_wire(("metal1","via1","metal2"),[in_pin, rail_position, rail_position - vector(0,self.m2_pitch)])
        self.add_via(layers=("metal1","via1","metal2"),
                     offset=in_pin + self.m1m2_via_offset,
                     rotate=90)

    def connect_rail_from_left_m2m3(self,inst, pin, rail):
        """ Helper routine to connect an unrotated/mirrored oriented instance to the rails """
        in_pin = inst.get_pin(pin).rc()
        rail_position = vector(self.rail_1_x_offsets[rail], in_pin.y)
        self.add_wire(("metal3","via2","metal2"),[in_pin, rail_position, rail_position - vector(0,self.m2_pitch)])
        self.add_via(layers=("metal1","via1","metal2"),
                     offset=in_pin + self.m1m2_via_offset,
                     rotate=90)
        self.add_via(layers=("metal2","via2","metal3"),
                     offset=in_pin + self.m2m3_via_offset,
                     rotate=90)
        
        
    def add_wen_routing(self):
        self.connect_rail_from_right(self.w_en_bar,"A","clk_bar")
        self.connect_rail_from_right(self.w_en_bar,"B","we")
        self.connect_rail_from_right(self.w_en_bar,"C","cs")

        # Connect the NAND3 output to the inverter
        # The pins are assumed to extend all the way to the cell edge
        w_en_bar_pin = self.w_en_bar.get_pin("Z").ur()
        inv_in_pin = self.pre_w_en.get_pin("A").ll()
        mid1 = vector(inv_in_pin.x,w_en_bar_pin.y)
        self.add_path("metal1",[w_en_bar_pin,mid1,inv_in_pin])
        

    
    def add_trien_routing(self):
        self.connect_rail_from_right(self.tri_en,"A","clk_buf")
        self.connect_rail_from_right(self.tri_en,"B","oe_bar")

        self.connect_rail_from_right_m2m3(self.tri_en_bar,"A","clk_bar")
        self.connect_rail_from_right_m2m3(self.tri_en_bar,"B","oe")


        

    def add_sen_routing(self):
        rbl_out_pin = self.rbl.get_pin("out").ul()
        in_pin = self.pre_s_en_bar.get_pin("A").rc()
        mid1 = vector(rbl_out_pin.x,in_pin.y)
        self.add_path("metal1",[rbl_out_pin,mid1,in_pin])                
        #s_en_pin = self.s_en.get_pin("Z").lc()

    
    def add_clk_routing(self):
        """ Route the clk and clk_bar signal internally """

        # clk_buf
        clk_buf_pin = self.clk_buf.get_pin("Z").rc()
        clk_buf_rail_position = vector(self.rail_1_x_offsets["clk_buf"], clk_buf_pin.y)
        self.add_wire(("metal1","via1","metal2"),[clk_buf_pin, clk_buf_rail_position, clk_buf_rail_position - vector(0,self.m2_pitch)])
                              
        # clk_bar
        self.connect_rail_from_left_m2m3(self.clk_bar,"Z","clk_bar")        
        
        # clk_buf to msf control flops
        msf_clk_pin = self.msf.get_pin("clk").bc()
        mid1 = msf_clk_pin - vector(0,self.m2_pitch)
        clk_buf_rail_position = vector(self.rail_1_x_offsets["clk_buf"], mid1.y)
        # route on M2 to allow vdd connection
        self.add_wire(("metal2","via1","metal1"),[msf_clk_pin, mid1, clk_buf_rail_position])        

    def connect_pin_to_output_pin(self, inst, pin_name, out_name):
        """ Create an output pin on the bottom side from the pin of a given instance. """
        out_pin = inst.get_pin(pin_name).center()
        self.add_via(layers=("metal1","via1","metal2"),
                     offset=out_pin + self.m1m2_via_offset,
                     rotate=90)
        self.add_layout_pin(text=out_name,
                            layer="metal2",
                            offset=out_pin.scale(1,0),
                            height=out_pin.y)
                            
    def add_output_routing(self):
        """ Output pin routing """
        self.connect_pin_to_output_pin(self.tri_en, "Z", "tri_en")
        self.connect_pin_to_output_pin(self.tri_en_bar, "Z", "tri_en_bar")
        self.connect_pin_to_output_pin(self.w_en, "Z", "w_en")        
        self.connect_pin_to_output_pin(self.s_en, "Z", "s_en")

    def add_supply_routing(self):

        rows_start = self.rail_1_start_x + self.overall_rail_1_gap
        rows_end = max(self.row_1_width,self.row_2_width,self.row_3_width)
        vdd_rail_position = vector(self.rail_1_x_offsets["vdd"], 0)
        well_width = drc["minwidth_well"]
        
        # M1 gnd rail from inv1 to max
        start_offset = self.clk_inv1.get_pin("gnd").lc()
        row1_gnd_end_offset = vector(rows_end,start_offset.y)
        self.add_path("metal1",[start_offset,row1_gnd_end_offset])
        rail_position = vector(self.rail_1_x_offsets["gnd"], start_offset.y)
        self.add_wire(("metal1","via1","metal2"),[vector(rows_start,start_offset.y), rail_position, rail_position + vector(0,self.m2_pitch)])

        # also add a well + around the rail
        self.add_rect(layer="pwell",
                      offset=vector(rows_start,start_offset.y),
                      width=rows_end-rows_start,
                      height=well_width)
        self.add_rect(layer="vtg",
                      offset=vector(rows_start,start_offset.y),
                      width=rows_end-rows_start,
                      height=well_width)

        # M1 vdd rail from inv1 to max
        start_offset = self.clk_inv1.get_pin("vdd").lc()
        row1_vdd_end_offset = vector(rows_end,start_offset.y)
        self.add_path("metal1",[start_offset,row1_vdd_end_offset])
        rail_position = vector(self.rail_1_x_offsets["vdd"], start_offset.y)
        self.add_wire(("metal1","via1","metal2"),[vector(rows_start,start_offset.y), rail_position, rail_position - vector(0,self.m2_pitch)])

        # also add a well +- around the rail
        self.add_rect(layer="nwell",
                      offset=vector(rows_start,start_offset.y)-vector(0,0.5*well_width),
                      width=rows_end-rows_start,
                      height=well_width)
        self.add_rect(layer="vtg",
                      offset=vector(rows_start,start_offset.y)-vector(0,0.5*well_width),
                      width=rows_end-rows_start,
                      height=well_width)

        
        # M1 gnd rail from inv1 to max
        start_offset = vector(rows_start, self.tri_en.get_pin("gnd").lc().y)
        row3_gnd_end_offset = vector(rows_end,start_offset.y)
        self.add_path("metal1",[start_offset,row3_gnd_end_offset])
        rail_position = vector(self.rail_1_x_offsets["gnd"], start_offset.y)
        self.add_wire(("metal1","via1","metal2"),[vector(rows_start,start_offset.y), rail_position, rail_position - vector(0,self.m2_pitch)])

        # also add a well +- around the rail
        self.add_rect(layer="pwell",
                      offset=vector(rows_start,start_offset.y)-vector(0,0.5*well_width),
                      width=rows_end-rows_start,
                      height=well_width)
        self.add_rect(layer="vtg",
                      offset=vector(rows_start,start_offset.y)-vector(0,0.5*well_width),
                      width=rows_end-rows_start,
                      height=well_width)                       

        
        # M1 vdd rail from inv1 to max
        start_offset = vector(rows_start, self.w_en_bar.get_pin("vdd").lc().y)
        row3_vdd_end_offset = vector(rows_end,start_offset.y)
        self.add_path("metal1",[start_offset,row3_vdd_end_offset])
        rail_position = vector(self.rail_1_x_offsets["vdd"], start_offset.y)
        self.add_wire(("metal1","via1","metal2"),[vector(rows_start,start_offset.y), rail_position, rail_position - vector(0,self.m2_pitch)])
        

        # Now connect the vdd and gnd rails between the replica bitline and the control logic
        (rbl_row3_gnd,rbl_row1_gnd) = self.rbl.get_pins("gnd")
        (rbl_row3_vdd,rbl_row1_vdd) = self.rbl.get_pins("vdd")        

        self.add_path("metal1",[row1_gnd_end_offset,rbl_row1_gnd.lc()])
        self.add_path("metal1",[row1_vdd_end_offset,rbl_row1_vdd.lc()])
        self.add_path("metal1",[row3_gnd_end_offset,rbl_row3_gnd.lc()])
        # row 3 may have a jog due to unequal row heights, so force the full overlap at the end
        self.add_path("metal1",[row3_vdd_end_offset - vector(self.m1_pitch,0),row3_vdd_end_offset,rbl_row3_vdd.lc()])
        

        # also add a well - around the rail
        self.add_rect(layer="nwell",
                      offset=vector(rows_start,start_offset.y)-vector(0,well_width),
                      width=rows_end-rows_start,
                      height=well_width)
        self.add_rect(layer="vtg",
                      offset=vector(rows_start,start_offset.y)-vector(0,well_width),
                      width=rows_end-rows_start,
                      height=well_width)


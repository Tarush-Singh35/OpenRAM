#!/usr/bin/env python3
# See LICENSE for licensing information.
#
# Copyright (c) 2016-2019 Regents of the University of California and The Board
# of Regents for the Oklahoma Agricultural and Mechanical College
# (acting for and on behalf of Oklahoma State University)
# All rights reserved.
#
import unittest
from testutils import *
import sys,os
sys.path.append(os.getenv("OPENRAM_HOME"))
import globals
from globals import OPTS
from sram_factory import factory
import debug

#@unittest.skip("SKIPPING 20_psram_1bank_2mux_test, wide metal supply routing error")
class psram_1bank_2mux_test(openram_test):

    def runTest(self):        
        globals.init_openram("config_{0}".format(OPTS.tech_name))
        from sram_config import sram_config
        OPTS.bitcell = "pbitcell"
        OPTS.replica_bitcell="replica_pbitcell"
        
        # testing layout of sram using pbitcell with 1 RW port (a 6T-cell equivalent)
        OPTS.num_rw_ports = 1
        OPTS.num_w_ports = 0
        OPTS.num_r_ports = 0
        
        c = sram_config(word_size=4,
                        num_words=32,
                        num_banks=1)
        c.num_words=32
        c.words_per_row=2
        c.recompute_sizes()
        debug.info(1, "Layout test for {}rw,{}r,{}w psram "
                   "with {} bit words, {} words, {} words per "
                   "row, {} banks".format(OPTS.num_rw_ports,
                                          OPTS.num_r_ports,
                                          OPTS.num_w_ports,
                                          c.word_size,
                                          c.num_words,
                                          c.words_per_row,
                                          c.num_banks))
        a = factory.create(module_type="sram", sram_config=c)
        self.local_check(a, final_verification=True)
        
        globals.end_openram()
        
# run the test from the command line
if __name__ == "__main__":
    (OPTS, args) = globals.parse_args()
    del sys.argv[1:]
    header(__file__, OPTS.tech_name)
    unittest.main(testRunner=debugTestRunner())

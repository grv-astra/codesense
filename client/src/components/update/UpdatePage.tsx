import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '../atomic/card'
import { ShieldCheck } from "lucide-react";
import ScanUpdate from './ScanUpdate';

function UpdatePage() {
  return (
    <div>
        <div className="grid grid-cols-2 gap-4 py-6">
            <Card className='shadow-lg border border-gray-200'>
                <ScanUpdate />
            </Card>

            <Card className="w-full rounded-2xl border border-gray-200 bg-white shadow-lg hover:shadow-xl transition-shadow">
                {/* Top section */}
                <CardHeader className="flex items-center gap-3 pb-2">
                    {/* Icon container */}
                    <div className="grid h-15 w-15 place-items-center rounded-lg bg-[#FCE9EC]">
                        <ShieldCheck className="h-10 w-10 text-[#BF0000]" />
                    </div>

                    <div>
                        <CardDescription className="text-md text-gray-500">Preset</CardDescription>
                        <CardTitle className="text-xl font-semibold leading-tight">Network Security Audit </CardTitle>
                    </div>
                </CardHeader>

                {/* Body copy */}
                <CardContent className="pt-0">
                    <CardDescription className="text-lg text-gray-800 pb-4">Description</CardDescription>
                    <p className="text-sm leading-relaxed text-gray-700">Comprehensive security scanning configuration with advanced threat detection and vulnerability assessment capabilities. </p>
                </CardContent>
            </Card>
        </div>


        <Card>

        </Card>

        
    </div>
  )
}

export default UpdatePage